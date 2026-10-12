"""Docker sandbox limits (BE-R10, D-10). Requires the sandbox image."""

from __future__ import annotations

import pytest

from app.sandbox import DockerSandbox

pytestmark = pytest.mark.docker

PASSING_TEST = "from solution import f\n\ndef test_f():\n    assert f() == 1\n"


def test_correct_code_passes(sandbox: DockerSandbox) -> None:
    result = sandbox.run_tests("def f():\n    return 1\n", PASSING_TEST)
    assert result.passed, result.output


def test_wrong_code_fails(sandbox: DockerSandbox) -> None:
    result = sandbox.run_tests("def f():\n    return 2\n", PASSING_TEST)
    assert not result.passed


def test_BE_AC09_network_is_blocked_and_run_continues(sandbox: DockerSandbox) -> None:
    code = (
        "import socket\n"
        "def f():\n"
        "    try:\n"
        "        socket.create_connection(('1.1.1.1', 80), timeout=2)\n"
        "        return 'connected'\n"
        "    except OSError:\n"
        "        return 'blocked'\n"
    )
    tests = "from solution import f\n\ndef test_net():\n    assert f() == 'blocked'\n"
    assert sandbox.run_tests(code, tests).passed
    # the sandbox is still usable afterwards ("the run continues")
    assert sandbox.run_tests("def f():\n    return 1\n", PASSING_TEST).passed


def test_BE_AC10_time_limit_kills_runaway_code(sandbox: DockerSandbox) -> None:
    fast = DockerSandbox(sandbox.image, time_limit_s=4)
    result = fast.run_tests("def f():\n    while True:\n        pass\n", PASSING_TEST)
    assert not result.passed
    assert result.timed_out


def test_memory_limit_stops_memory_bomb(sandbox: DockerSandbox) -> None:
    code = "def f():\n    blob = bytearray(1024 * 1024 * 1024)\n    return len(blob)\n"
    result = sandbox.run_tests(code, PASSING_TEST)
    assert not result.passed


def test_filesystem_is_read_only_and_user_is_not_root(sandbox: DockerSandbox) -> None:
    code = (
        "import os\n"
        "def f():\n"
        "    try:\n"
        "        open('/work/hack.txt', 'w').write('x')\n"
        "        return 'writable'\n"
        "    except OSError:\n"
        "        return os.getuid()\n"
    )
    tests = "from solution import f\n\ndef test_ro():\n    assert f() == 65534\n"
    assert sandbox.run_tests(code, tests).passed
