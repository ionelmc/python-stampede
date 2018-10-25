import json
import os
import pwd
import select
import signal
import socket
import struct
from contextlib import closing
from logging import getLogger

import signalfd

from .lock import FileLock
from .utils import cloexec
from .utils import close
from .utils import collect_sigchld

logger = getLogger(__name__)

SO_PEERCRED = 17


class Workspace(object):
    def __init__(self, key):
        self.key = key
        self.clients = []
        self.started = False

    @property
    def formatted_clients(self):
        return ", ".join(i for _, _, i in self.clients)

    def __str__(self):
        return "Workspace(%s, clients=[%s])" % (
            self.key,
            self.formatted_clients,
        )

    __repr__ = __str__


class SingleInstanceMeta(type):
    __inst = None

    def __call__(cls, path, *args, **kwargs):
        if cls.__inst is not None:
            raise RuntimeError("Only 1 instance allowed!")

        lock = FileLock(path)
        if lock.acquire():
            inst = cls.__inst = super(SingleInstanceMeta, cls).__call__(path, *args, **kwargs)
            return inst
        else:
            return StampedeStub()


class StampedeStub(object):
    def run(self):
        pass


class StampedeWorker(SingleInstanceMeta("StampedeWorkerBase", (object,), {})):
    queues = {}
    clients = {}
    tasks = {}
    alarm_time = 5 * 60  # abort in 5 minutes if no progress
    socket_backlog = 5

    def __init__(self, path):
        self.socket_path = "%s.sock" % path

    def notify_progress(self, *_a, **_kw):
        signal.alarm(self.alarm_time)

    def process_workspace(self, workspace):
        if not workspace.started:
            workspace.started = True
            pid = os.fork()
            if pid:
                self.tasks[pid] = workspace
                logger.info("Started task %r for %s", pid, workspace)
            else:
                logger.info("Running task %r key=%s", os.getpid(), workspace.key)
                exit_code = 255
                try:
                    try:
                        self.notify_progress()
                        self.handle_task(workspace.key)
                        logger.info("Completed task %r key=%s", os.getpid(), workspace.key)
                    except Exception:
                        logger.exception("Failed task %r key=%s", os.getpid(), workspace.key)
                    except SystemExit as exc:
                        exit_code = exc.code
                        logger.exception("Failed task %r key=%s", os.getpid(), workspace.key)
                    else:
                        exit_code = 0
                finally:
                    os._exit(exit_code)

    def handle_task(self, key):
        raise NotImplementedError()

    def handle_signal(self, child_signals):
        for pid, exit_code in collect_sigchld(child_signals).items():
            if pid not in self.tasks:
                logger.warn("Got SIGCHLD for unknown pid: %s", pid)
                continue
            workspace = self.tasks.pop(pid)
            self.queues.pop(workspace.key)
            logger.info("Task %r completed. Passing back results to [%s]", pid, workspace.formatted_clients)
            while workspace.clients:
                fd, conn, client_id = workspace.clients.pop()
                try:
                    with closing(fd):
                        with closing(conn):
                            conn.write(json.dumps({"exit_code": exit_code, "pid": pid}).encode('ascii'))
                        fd.shutdown(socket.SHUT_RDWR)
                except Exception as exc:
                    logger.error("Failed to send response to %s: %s", client_id, exc)

    def handle_request(self, fd):
        conn, client_id = self.clients.pop(fd)
        try:
            key = conn.readline().strip()
            if not key:
                # this is meant to support basic connect health checks
                # (avoid having log garbage for healthcheck requests)
                logger.info("Got empty request from client %s", client_id)
                close(conn, fd)
                return
            if key in self.queues:
                workspace = self.queues[key]
            else:
                workspace = self.queues.setdefault(key, Workspace(key))
            workspace.clients.append((fd, conn, client_id))
            self.process_workspace(workspace)
        except Exception:
            logger.exception("Failed to read request from client %s", client_id)
            close(conn, fd)
            raise

    def handle_accept(self, requests_sock):
        client_sock, _ = requests_sock.accept()
        cloexec(client_sock)
        pid, uid, gid = struct.unpack(b"3i", client_sock.getsockopt(
            socket.SOL_SOCKET, SO_PEERCRED, struct.calcsize(b"3i")
        ))
        client_sock.settimeout(1)  # fail fast as .readline() can block
        self.clients[client_sock] = client_sock.makefile("rwb"), "%s:%s" % (pwd.getpwuid(uid).pw_name, pid)

    def run(self):
        child_fd = signalfd.signalfd(-1, [signal.SIGCHLD], signalfd.SFD_NONBLOCK | signalfd.SFD_CLOEXEC)
        with os.fdopen(child_fd, "rb") as child_signals:
            signalfd.sigprocmask(signalfd.SIG_BLOCK, [signal.SIGCHLD])
            with closing(cloexec(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))) as requests_sock:
                logger.info("Binding to %r", self.socket_path)
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)
                pending_socket_path = "%s-pending" % self.socket_path
                requests_sock.bind(pending_socket_path)
                requests_sock.listen(self.socket_backlog)
                os.rename(pending_socket_path, self.socket_path)
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
