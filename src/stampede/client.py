import os
import socket
from contextlib import closing
from logging import getLogger
from os.path import exists
from time import sleep
from time import time

from .lock import FileLock
from .utils import IS_PY2

logger = getLogger(__name__)


def request(path, data, wait=True):
    logger.info("request(%r, %r, wait=%s)", path, data, wait)
    if b"\n" in data or b"\r" in data:
        raise RuntimeError("Request data must not have line endings!")
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with closing(sock):
            sock.settimeout(None)
            sock.connect("%s.sock" % path)
            if IS_PY2:
                fh = sock.makefile(bufsize=0)
            else:
                fh = sock.makefile("rwb", buffering=0)
            fh.write(b"%s\n" % data)
            if not wait:
                return
            line = fh.readline()
            if not line.startswith(b"done"):
                raise RuntimeError("Request failed: %r. Check the logs !" % line)
            logger.info("request(%r, %r, wait=%s) - DONE.", path, data, wait)
            return line
    except Exception:
        logger.exception("request(%r, %r, wait=%s) - FAILED:", path, data, wait)
        raise


def request_and_spawn(cli, path, data, wait=True, timeout=1):
    socket_path = "%s.sock" % path
    if exists(socket_path):
        logger.debug("request_and_spawn(%r, %r, %r, wait=%s) - %s already exists. Checking if lock active ...",
                     cli, path, data, wait, socket_path)
        lock = FileLock(path)
        if lock.acquire():
            logger.debug("request_and_spawn(%r, %r, %r, wait=%s) - Not locked. Spawning daemon ...",
                         cli, path, data, wait)
            lock.release()
            os.unlink(socket_path)
            os.spawnl(os.P_NOWAIT, *cli)
    else:
        logger.debug("request_and_spawn(%r, %r, %r, wait=%s) - %s doesn't exist. Spawning daemon ...",
                     cli, path, data, wait, socket_path)
        os.spawnl(os.P_NOWAIT, *cli)

    t = time()
    while not exists(socket_path) and time() - t < timeout:
        sleep(0.01)

    return request(path, data, wait=wait)
