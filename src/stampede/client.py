import os
import socket
import sys
from contextlib import closing
from os.path import exists
from logging import getLogger

from .lock import FileLock

logger = getLogger(__name__)


def request(path, data, async=False):
    logger.info("request(%r, %r, async=%s)", path, data, async)
    if '\n' in data or '\r' in data:
        raise RuntimeError('Request data must not have line endings!')
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with closing(sock):
            sock.settimeout(None)
            sock.connect('%s.sock' % path)
            fh = sock.makefile(bufsize=0)
            fh.write("%s\n" % data)
            if async:
                return
            line = fh.readline()
            if not line.startswith('done'):
                raise RuntimeError("Request failed: %r. Check the logs !" % line)
            logger.info("request(%r, %r, async=%s) - DONE.", path, data, async)
            return line
    except Exception:
        logger.exception("request(%r, %r, async=%s) - FAILED:", path, data, async)
        raise


def request_and_spawn(cli, path, data, async=False):
    socket_path = '%s.sock' % path
    if exists(socket_path):
        lock = FileLock(path)
        if lock.acquire():
            lock.release()
            os.spawnl(os.P_NOWAIT, sys.executable, '-m', cli)
    else:
        os.spawnl(os.P_NOWAIT, sys.executable, '-m', cli)

    request(path, data, async=async)
