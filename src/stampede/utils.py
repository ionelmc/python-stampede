import errno
import fcntl
import os
import signal
import sys
from collections import namedtuple
from logging import getLogger

import signalfd

logger = getLogger(__name__)

ProcessExit = namedtuple("ProcessExit", ["pid", "status"])
IS_PY2 = sys.version_info[0] == 2


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
            if closeok and exc.errno == errno.EBADF:
                logger.critical("Can't read any more events from signalfd (it's closed).")
            elif exc.errno not in (errno.EAGAIN, errno.EINTR):
                raise exc
            if IS_PY2:
                sys.exc_clear()
            break
        else:
            assert si.ssi_signo == signal.SIGCHLD
            try:
                os.waitpid(si.ssi_pid, os.WNOHANG)
            except OSError as exc:
                if exc.errno != errno.ECHILD:
                    raise
            pending[si.ssi_pid] = si.ssi_status

    while True:
        ret = wait_pid()
        if ret:
            pending[ret.pid] = ret.status
        else:
            break
    return pending


def wait_pid(pid=0, mode=os.WNOHANG):
    while True:
        try:
            exit_pid, exit_status = os.waitpid(pid, mode)
        except OSError as exc:
            if exc.errno == errno.EINTR:
                continue
            if exc.errno != errno.ECHILD:
                raise
            if IS_PY2:
                sys.exc_clear()
            break
        else:
            if not exit_pid:
                break

            elif os.WIFEXITED(exit_status):
                return ProcessExit(exit_pid, os.WEXITSTATUS(exit_status))
            elif os.WIFSIGNALED(exit_status):
                return ProcessExit(exit_pid, -os.WTERMSIG(exit_status))
            elif os.WIFSTOPPED(exit_status):
                return ProcessExit(exit_pid, os.WSTOPSIG(exit_status))
    return None
