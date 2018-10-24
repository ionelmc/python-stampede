import os
import pwd
import socket
import sys
import time
from contextlib import closing
from contextlib import contextmanager

import psutil
import pytest
from process_tests import TestProcess
from process_tests import dump_on_error
from process_tests import wait_for_strings
from psutil import STATUS_ZOMBIE
from subprocess32 import DEVNULL
from subprocess32 import Popen

from stampede import client
from stampede.client import TaskFailed

import helper

UDS_PATH = '%s.sock' % helper.PATH
TIMEOUT = int(os.getenv('TEST_TIMEOUT', 5))
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


def test_prespawned():
    with TestProcess(sys.executable, helper.__file__, 'simple') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            response = client.request(helper.PATH, b"foobar")
            assert response.exit_code == 0
            wait_for_strings(proc.read, TIMEOUT,
                             '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()),
                             'JOB foobar EXECUTED',
                             'completed. Passing back results to',
                             'Queues => 0 workspaces')


def test_bad_request():
    pytest.raises(ValueError, client.request, UDS_PATH, b"foo\nbar")
    with pytest.raises(TypeError, match='key should be bytes, not .*'):
        client.request(UDS_PATH, u"foo\nbar")


@pytest.fixture(params=['dead', 'running', 'clean'])
def setup_request_and_spawn(request):
    def setup(helper_entrypoint):
        if request.param == 'clean':
            if os.path.exists(UDS_PATH):
                os.unlink(UDS_PATH)
        elif request.param == 'running':
            Popen([sys.executable, helper.__file__, helper_entrypoint], stdin=DEVNULL, close_fds=True)
            t = time.time()
            while not os.path.exists(UDS_PATH) and time() - t < 5:
                time.sleep(0.01)
        elif request.param == 'dead':
            if os.path.exists(UDS_PATH):
                os.unlink(UDS_PATH)
            with closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as sock:
                sock.bind(UDS_PATH)
        else:
            raise RuntimeError("Unknown param %r" % request.param)
    setup.kind = request.param

    yield setup

    for child in psutil.Process(os.getpid()).children(recursive=True):
        child.kill()
        child.wait()

    assert len(psutil.Process(os.getpid()).children()) == 0


@pytest.fixture(params=[True, False], ids=['fail', 'success'])
def request_and_spawn(request, setup_request_and_spawn):
    if request.param:
        entrypoint = 'fail'

        def request_and_spawn_wrapper(wait=True):
            if wait:
                with pytest.raises(TaskFailed, match=r"Task failed with exit_code: 255 \(pid: .*\)") as exc_info:
                    client.request_and_spawn([sys.executable, helper.__file__, entrypoint], helper.PATH, b"foobar")
                assert exc_info.value.exit_code == 255
                assert isinstance(exc_info.value.pid, int)
            else:
                client.request_and_spawn([sys.executable, helper.__file__, entrypoint], helper.PATH, b"foobar",
                                         wait=False)
    else:
        entrypoint = 'simple'

        def request_and_spawn_wrapper(wait=True):
            if wait:
                result = client.request_and_spawn([sys.executable, helper.__file__, entrypoint], helper.PATH, b"foobar")
                assert result.exit_code == 0
                assert isinstance(result.pid, int)
            else:
                client.request_and_spawn([sys.executable, helper.__file__, entrypoint], helper.PATH, b"foobar",
                                         wait=False)

    setup_request_and_spawn(entrypoint)
    request_and_spawn_wrapper.kind = setup_request_and_spawn.kind

    yield request_and_spawn_wrapper


def get_children():
    return [
        proc
        for proc in psutil.Process(os.getpid()).children(recursive=True)
        if proc.is_running() and proc.status() != STATUS_ZOMBIE
    ]


def test_request_and_spawn(capfd, request_and_spawn):
    request_and_spawn()

    captured = capfd.readouterr()
    print('**************\n%s\n**************' % captured.err)

    if request_and_spawn.kind != 'running':
        assert '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()) in captured.err
        assert 'completed. Passing back results to' in captured.err
        assert 'Queues => 0 workspaces' in captured.err

    request_and_spawn(wait=False)
    request_and_spawn(wait=False)
    request_and_spawn(wait=False)
    request_and_spawn(wait=False)
    request_and_spawn()

    # wait for process list to settle (eg: there might be one or two extra processes that will exit because the lock
    # is already acquired - see StampedeStub)
    start = time.time()
    while len(get_children()) > 1 and time.time() - start < TIMEOUT:
        time.sleep(0.1)

    children = get_children()
    assert len(children) == 1
    for child in children:
        child.kill()

    captured = capfd.readouterr()
    print('##############\n%s\n##############' % captured.err)
    if request_and_spawn.kind != 'running':
        assert '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()) in captured.err
        assert 'completed. Passing back results to' in captured.err
        assert 'Queues => 0 workspaces' in captured.err
