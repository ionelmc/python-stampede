import os
import socket
import sys
from contextlib import closing
from os.path import exists
from logging import getLogger
from time import time, sleep

from .lock import FileLock
from .utils import IS_PY2

logger = getLogger(__name__)


def request(path, data, async=False):
    logger.info("request(%r, %r, async=%s)", path, data, async)
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
            if async:
                return
            line = fh.readline()
            if not line.startswith(b"done"):
                raise RuntimeError("Request failed: %r. Check the logs !" % line)
            logger.info("request(%r, %r, async=%s) - DONE.", path, data, async)
            return line
    except Exception:
        logger.exception("request(%r, %r, async=%s) - FAILED:", path, data, async)
        raise


def request_and_spawn(cli, path, data, async=False, timeout=1):
    socket_path = "%s.sock" % path
    if exists(socket_path):
        logger.debug("request_and_spawn(%r, %r, %r, async=%s) - %s already exists. Checking if lock active ...",
                     cli, path, data, async, socket_path)
        lock = FileLock(path)
        if lock.acquire():
            logger.debug("request_and_spawn(%r, %r, %r, async=%s) - Not locked. Spawning daemon ...",
                         cli, path, data, async)
            lock.release()
            os.unlink(socket_path)
            os.spawnl(os.P_NOWAIT, *cli)
    else:
        logger.debug("request_and_spawn(%r, %r, %r, async=%s) - %s doesn't exist. Spawning daemon ...",
                     cli, path, data, async, socket_path)
        os.spawnl(os.P_NOWAIT, *cli)

    t = time()
    while not exists(socket_path) and time() - t < timeout:
        sleep(0.01)

    return request(path, data, async=async)
