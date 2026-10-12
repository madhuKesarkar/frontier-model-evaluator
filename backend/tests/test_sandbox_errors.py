"""A broken sandbox is a harness failure, never a model defect (BE-R3, BE-R10).

Found by the Phase 3 E2E run: with the Docker daemon down, `docker run` exits 1 (like a
failing pytest), so code tasks were scored as INCORRECT_CODE S2 defects.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from app.sandbox import DockerSandbox, SandboxUnavailable

DAEMON_DOWN = (
    "docker: Cannot connect to the Docker daemon at unix:///var/run/docker.sock. "
    "Is the docker daemon running?"
)


def fake_docker(monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str, stderr: str) -> None:
    monkeypatch.setattr("app.sandbox.shutil.which", lambda _: "/usr/bin/docker")

    def run(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    monkeypatch.setattr("app.sandbox.subprocess.run", run)


def test_daemon_down_raises_instead_of_failing_the_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_docker(monkeypatch, 1, "", DAEMON_DOWN)
    with pytest.raises(SandboxUnavailable, match="Cannot connect"):
        DockerSandbox("fme-sandbox:1").run_tests("def f(): return 1", "def test(): pass")


def test_missing_image_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_docker(monkeypatch, 125, "", "Unable to find image 'fme-sandbox:1' locally")
    with pytest.raises(SandboxUnavailable):
        DockerSandbox("fme-sandbox:1").run_tests("def f(): return 1", "def test(): pass")


def test_genuine_pytest_failure_is_still_a_failed_result(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_docker(monkeypatch, 1, "F\n1 failed in 0.01s", "")
    result = DockerSandbox("fme-sandbox:1").run_tests("def f(): return 2", "def test(): ...")
    assert not result.passed
    assert "1 failed" in result.output


def test_check_fails_fast_when_daemon_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_docker(monkeypatch, 1, "", DAEMON_DOWN)
    with pytest.raises(SandboxUnavailable, match="Cannot connect"):
        DockerSandbox("fme-sandbox:1").check()


def test_check_passes_when_image_is_present(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_docker(monkeypatch, 0, "sha256:abc\n", "")
    DockerSandbox("fme-sandbox:1").check()
