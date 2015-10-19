import os
import pwd
import socket
import sys
import time
from contextlib import closing
from contextlib import contextmanager

import pytest
from process_tests import TestProcess
from process_tests import dump_on_error
from process_tests import wait_for_strings

UDS_PATH = '/tmp/stampede-tests.sock'
HELPER = os.path.join(os.path.dirname(__file__), "helper.py")
TIMEOUT = int(os.getenv('REDIS_LOCK_TEST_TIMEOUT', 5))
PY3 = sys.version_info[0] == 3


@contextmanager
def connection(timeout=1):
    with closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as sock:
        sock.settimeout(timeout)
        sock.connect(UDS_PATH)
        if PY3:
            fh = sock.makefile("rwb", buffering=0)
        else:
            fh = sock.makefile(bufsize=0)
        with closing(fh):
            yield fh


def test_simple():
    with TestProcess(sys.executable, HELPER, 'test_simple') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            with connection() as fh:
                fh.write(b"first")
                fh.write(b"-second\n")
                line = fh.readline()
                assert line.startswith(b'done (job:'), line
                wait_for_strings(proc.read, TIMEOUT,
                                      '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()),
                                      'JOB first-second EXECUTED',
                                      'completed. Passing back results to',
                                      'Queues => 0 workspaces',
                                      )


def test_fail():
    with TestProcess(sys.executable, HELPER, 'test_fail') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            with connection() as fh:
                fh.write(b"first")
                fh.write(b"-second\n")
                line = fh.readline()
                assert line.startswith(b'done (job:'), line
                wait_for_strings(proc.read, TIMEOUT,
                                      '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()),
                                      'Failed job',
                                      'Exception: FAIL',
                                      'Queues => 0 workspaces',
                                      )


def test_incomplete_request():
    with TestProcess(sys.executable, HELPER, 'test_simple') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            with connection(2) as fh:
                fh.write(b"first")
                line = fh.readline()
                assert line == b''
                wait_for_strings(proc.read, TIMEOUT,
                                      'Failed to read request from client %s:%s' % (
                                          pwd.getpwuid(os.getuid())[0], os.getpid()),
                                      )


def test_queue_collapse():
    with TestProcess(sys.executable, HELPER, 'test_queue_collapse') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            clients = []
            for _ in range(5):
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect(UDS_PATH)
                if PY3:
                    fh = sock.makefile("rwb", buffering=0)
                else:
                    fh = sock.makefile(bufsize=0)
                fh.write(b"test_queue_collapse\n")
                clients.append((fh, sock))
            try:
                t1 = time.time()
                result = [fh.readline() for fh, _ in clients]
                delta = time.time() - t1
                if delta > TIMEOUT:
                    fail('Jobs took too much time (%0.2f sec)' % delta)
                wait_for_strings(proc.read, TIMEOUT,
                                      'test_queue_collapse OK',
                                      '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()),
                                      )
            finally:
                [(fh.close(), sock.close()) for fh, sock in clients]


def test_timeout():
    with TestProcess(sys.executable, HELPER, 'test_timeout') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            with connection(3) as fh:
                fh.write(b"test_timeout\n")
                line = fh.readline()
                assert line.startswith(b'fail:14 (job:'), line
                wait_for_strings(proc.read, TIMEOUT,
                                      '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()),
                                      'test_timeout STARTED',
                                      'completed. Passing back results to',
                                      )
                assert 'test_timeout FAIL' not in proc.read()


def test_bad_client():
    with TestProcess(sys.executable, HELPER, 'test_simple') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect(UDS_PATH)
            if PY3:
                fh = sock.makefile("rwb", buffering=0)
            else:
                fh = sock.makefile(bufsize=0)

            fh.write(b"first-second\n")
            fh.close()
            sock.close()
            time.sleep(0.2)
            assert proc.is_alive
            wait_for_strings(proc.read, TIMEOUT,
                                  '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()),
                                  'JOB first-second EXECUTED',
                                  'completed. Passing back results to',
                                  'Failed to send response to ',
                                  )


def test_highlander():
    from stampede import StampedeWorker
    man = StampedeWorker()
    with pytest.raises(RuntimeError):
        StampedeWorker()
