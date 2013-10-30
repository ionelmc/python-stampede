# encoding: utf-8
from logging import getLogger
logger = getLogger(__name__)

import os
import sys
import fcntl
import errno
import socket
import signalfd
import signal
import select
import struct
import pwd
from contextlib import closing
from ctypes import Structure, c_uint32, c_char, c_int32, c_uint64

SO_PEERCRED = 17

class signalfd_siginfo(Structure):
    _fields_ = (
        ('ssi_signo', c_uint32),    # Signal number
        ('ssi_errno', c_int32),     # Error number (unused)
        ('ssi_code', c_int32),      # Signal code
        ('ssi_pid', c_uint32),      # PID of sender
        ('ssi_uid', c_uint32),      # Real UID of sender
        ('ssi_fd', c_int32),        # File descriptor (SIGIO)
        ('ssi_tid', c_uint32),      # Kernel timer ID (POSIX timers)
        ('ssi_band', c_uint32),     # Band event (SIGIO)
        ('ssi_overrun', c_uint32),  # POSIX timer overrun count
        ('ssi_trapno', c_uint32),   # Trap number that caused signal
        ('ssi_status', c_int32),    # Exit status or signal (SIGCHLD)
        ('ssi_int', c_int32),       # Integer sent by sigqueue(2)
        ('ssi_ptr', c_uint64),      # Pointer sent by sigqueue(2)
        ('ssi_utime', c_uint64),    # User CPU time consumed (SIGCHLD)
        ('ssi_stime', c_uint64),    # System CPU time consumed (SIGCHLD)
        ('ssi_addr', c_uint64),     # Address that generated signal
                                    # (for hardware-generated signals)
        ('_padding', c_char * 46),  # Pad size to 128 bytes (allow for
                                    # additional fields in the future)
    )


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
            raise RuntimeError("THERE CAN BE ONLY ONE !") # You cannot make more than 1 instance of a Highlander class, it's too dangerous to have 2 !
        man = super(Highlander, cls).__call__(*args, **kwargs)
        cls.born = True
        return man


class StampedeWorker(Highlander("StampedeWorkerBase", (object,), {})):

    queues = {}
    clients = {}
    jobs = {}
    alarm_time = 5 * 60 # 5 minutes
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
        si = signalfd_siginfo()
        try:
            child_signals.readinto(si)
        except IOError as exc:
            if exc.errno == errno.EAGAIN:
                logger.critical("Got %s for child_fd:%s", exc, child_signals)
                return
            raise

        assert si.ssi_signo == signal.SIGCHLD
        os.waitpid(si.ssi_pid, os.WNOHANG)
        workspace = self.jobs.pop(si.ssi_pid)
        logger.info("Job %r completed. Passing back results to [%s]", si.ssi_pid, workspace.formatted_active)
        while workspace.active:
            fd, conn, client_id = workspace.active.pop()
            with closing(fd):
                try:
                    with closing(conn):
                        conn.write(('%s (job: %d)\n' % (
                            'done' if si.ssi_status == 0
                                   else 'fail:%d' % si.ssi_status,
                            si.ssi_pid
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
        client_sock.settimeout(1) # fail fast as .readline() can block
        self.clients[client_sock] = client_sock.makefile('rwb'), "%s:%s" % (pwd.getpwuid(uid).pw_name, pid)

    def run(self):
        child_fd = signalfd.signalfd(0, [signal.SIGCHLD], signalfd.SFD_NONBLOCK|signalfd.SFD_CLOEXEC)
        with os.fdopen(child_fd, 'rb') as child_signals:
            signalfd.sigprocmask(signalfd.SIG_BLOCK, [signal.SIGCHLD])
            with closing(cloexec(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))) as requests_sock:
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

if __name__ == '__main__': # pragma: no cover
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='[pid=%(process)d - %(asctime)s]: %(name)s - %(levelname)s - %(message)s',
    )

    class MacLeod(StampedeWorker):
        socket_name = 'test.sock'

        def do_work(self, workspace_name):
            import time
            time.sleep(18)

    man = MacLeod()
    man.run()
