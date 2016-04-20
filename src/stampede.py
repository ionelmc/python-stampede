# encoding: utf-8
import errno
import fcntl
import os
import pwd
import select
import signal
import socket
import struct
import sys
from contextlib import closing
from logging import getLogger

import signalfd

logger = getLogger(__name__)

SO_PEERCRED = 17


def close(*fds):
    for fd in fds:
        safe_close(fd)


def safe_close(fd):
    try:
        if isinstance(fd, int):
            os.close(fd)
        else:
            fd.close()
    except Exception as exc:
        logger.critical("Ignored error %s when closing fd %s", exc, fd)


def cloexec(fd):
    fcntl.fcntl(fd, fcntl.F_SETFD, fcntl.fcntl(fd, fcntl.F_GETFD) | fcntl.FD_CLOEXEC)
    return fd


def collect_sigchld(sigfd, closeok=False):
    pending = {}

    while True:
        try:
            si = signalfd.read_siginfo(sigfd)
        except (OSError, IOError) as exc:
            if close and exc.errno == errno.EBADF:
                logger.critical("Can't read any more events from signalfd (it's closed).")
            elif exc.errno != errno.EAGAIN:
                raise exc

            sys.exc_clear()
            break
        else:
            assert si.ssi_signo == signal.SIGCHLD
            try:
                os.waitpid(si.ssi_pid, os.WNOHANG)
            except OSError as exc:
                if exc.errno == errno.ECHILD:
                    pending[si.ssi_pid] = -errno.ECHILD
                else:
                    raise
            else:
                pending[si.ssi_pid] = si.ssi_status

    while True:
        try:
            pid, exit_code = os.waitpid(0, os.WNOHANG)
        except OSError as exc:
            if exc.errno != 10:
                raise
            sys.exc_clear()
            break
        else:
            if not pid:
                break
            if pid not in pending:
                if os.WIFEXITED(exit_code):
                    pending[pid] = os.WEXITSTATUS(exit_code)
                elif os.WIFSIGNALED(exit_code):
                    pending[pid] = os.WTERMSIG(exit_code)
                elif os.WIFSTOPPED(exit_code):
                    pending[pid] = os.WSTOPSIG(exit_code)
    return pending


class Workspace(object):
    def __init__(self, name):
        self.name = name
        self.queue = []
        self.active = None

    @property
    def is_dead(self):
        return not self.queue and not self.active

    @property
    def formatted_active(self):
        return ', '.join(i for _, _, i in self.active)

    @property
    def formatted_queue(self):
        return ', '.join(i for _, _, i in self.queue)

    def __str__(self):
        return "Workspace(%s, active=[%s], queue=[%s])" % (
            self.name,
            self.formatted_active,
            self.formatted_queue,
        )

    __repr__ = __str__


class Highlander(type):
    born = False

    def __call__(cls, *args, **kwargs):
        if cls.born:
            raise RuntimeError(
                "THERE CAN BE ONLY ONE !")  # You cannot make more than 1 instance of a Highlander class,
            # it's too dangerous to have 2 !
        man = super(Highlander, cls).__call__(*args, **kwargs)
        cls.born = True
        return man


class StampedeWorker(Highlander("StampedeWorkerBase", (object,), {})):
    queues = {}
    clients = {}
    jobs = {}
    alarm_time = 5 * 60  # 5 minutes
    socket_backlog = 5

    def notify_progress(self, *_a, **_kw):
        signal.alarm(self.alarm_time)

    def process_workspace(self, workspace):
        if not workspace.active and workspace.queue:
            pid = os.fork()
            if pid:
                workspace.active = workspace.queue
                workspace.queue = []
                self.jobs[pid] = workspace
                logger.info("Started job %r for %s", pid, workspace)
            else:
                logger.info("Running job %r workspace_name=%s", os.getpid(), workspace.name)
                try:
                    self.notify_progress()
                    self.do_work(workspace.name)
                    logger.info("Completed job %r workspace_name=%s", os.getpid(), workspace.name)
                except Exception:
                    logger.exception("Failed job %r workspace_name=%s", os.getpid(), workspace.name)
                finally:
                    close(*self.clients.keys())
                    os._exit(0)

    def do_work(self, workspace_name):
        raise NotImplementedError()

    def handle_signal(self, child_signals):
        for pid, exit_code in collect_sigchld(child_signals).items():
            workspace = self.jobs.pop(pid)
            logger.info("Job %r completed. Passing back results to [%s]", pid, workspace.formatted_active)
            while workspace.active:
                fd, conn, client_id = workspace.active.pop()
                with closing(fd):
                    try:
                        with closing(conn):
                            conn.write(('%s (job: %d)\n' % (
                                'done' if exit_code == 0
                                else 'fail:%d' % exit_code,
                                pid
                            )).encode('ascii'))
                        fd.shutdown(socket.SHUT_RDWR)
                    except EnvironmentError:
                        logger.exception("Failed to send response to %s", client_id)
            self.process_workspace(workspace)
            if workspace.is_dead:
                self.queues.pop(workspace.name)

    def handle_request(self, fd):
        conn, client_id = self.clients.pop(fd)
        try:
            workspace_name = conn.readline().strip()
            if workspace_name in self.queues:
                workspace = self.queues[workspace_name]
            else:
                workspace = self.queues.setdefault(workspace_name, Workspace(workspace_name))
            workspace.queue.append((fd, conn, client_id))
            self.process_workspace(workspace)
        except Exception:
            logger.exception('Failed to read request from client %s', client_id)
            close(conn, fd)
            raise

    def handle_accept(self, requests_sock):
        client_sock, _ = requests_sock.accept()
        cloexec(client_sock)
        pid, uid, gid = struct.unpack(b'3i', client_sock.getsockopt(
            socket.SOL_SOCKET, SO_PEERCRED, struct.calcsize(b'3i')
        ))
        client_sock.settimeout(1)  # fail fast as .readline() can block
        self.clients[client_sock] = client_sock.makefile('rwb'), "%s:%s" % (pwd.getpwuid(uid).pw_name, pid)

    def run(self):
        child_fd = signalfd.signalfd(-1, [signal.SIGCHLD], signalfd.SFD_NONBLOCK | signalfd.SFD_CLOEXEC)
        with os.fdopen(child_fd, 'rb') as child_signals:
            signalfd.sigprocmask(signalfd.SIG_BLOCK, [signal.SIGCHLD])
            with closing(cloexec(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))) as requests_sock:
                logger.info("Binding to %r", self.socket_name)
                if os.path.exists(self.socket_name):
                    os.unlink(self.socket_name)
                requests_sock.bind(self.socket_name)
                requests_sock.listen(self.socket_backlog)
                try:
                    while 1:
                        qlen = len(self.queues)
                        logger.debug("Queues => %s workspaces", qlen)
                        for i, wq in enumerate(self.queues.values()):
                            if i + 1 == qlen:
                                logger.debug(" \_ %s", wq)
                            else:
                                logger.debug(" |_ %s", wq)

                        current_fds = [child_fd, requests_sock]
                        current_fds.extend(self.clients.keys())
                        read_ready, _, errors = select.select(current_fds, [], current_fds, 1)
                        for fd in read_ready:
                            if requests_sock == fd:
                                self.handle_accept(requests_sock)
                            elif fd in self.clients:
                                self.handle_request(fd)
                            elif fd == child_fd:
                                self.handle_signal(child_signals)
                        for fd in errors:
                            logger.error("Fd %r has error !", fd)
                finally:
                    for fd, (fh, _) in self.clients.items():
                        close(fh, fd)

