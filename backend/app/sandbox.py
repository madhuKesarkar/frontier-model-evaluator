"""Docker sandbox for running model-written code (backend-spec BE-R10, D-10, D-15).

Every execution gets a fresh container with: no network, 512 MB memory (no swap),
1 CPU, 64 processes, non-root user, read-only root filesystem, a small /tmp, and a
hard 10-second wall-clock limit. The code and tests are mounted read-only.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from app.checkers import RunResult

TIME_LIMIT_S = 10  # D-10
MEMORY_LIMIT = "512m"  # D-10


# Messages the docker CLI prints when it cannot reach the daemon. The CLI then exits
# with 1, the same code as a failing pytest, so the exit code alone can't tell them apart.
DAEMON_DOWN_MARKERS = ("Cannot connect to the Docker daemon", "error during connect")


class SandboxUnavailable(RuntimeError):
    """The sandbox itself failed (daemon down, image missing): never the model's fault."""


class DockerSandbox:
    def __init__(self, image: str, time_limit_s: int = TIME_LIMIT_S) -> None:
        if shutil.which("docker") is None:
            raise SandboxUnavailable("docker is not installed")
        self.image = image
        self.time_limit_s = time_limit_s

    def check(self) -> None:
        """Fail fast before a run: the daemon must answer and the image must exist."""
        cmd = ["docker", "image", "inspect", "--format", "{{.Id}}", self.image]
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise SandboxUnavailable(proc.stderr.strip()[-500:] or "docker image inspect failed")

    def run_tests(self, solution: str, tests: str) -> RunResult:
        name = f"fme-sbx-{uuid.uuid4().hex[:12]}"
        with tempfile.TemporaryDirectory(prefix="fme-sbx-") as tmp:
            work = Path(tmp)
            (work / "solution.py").write_text(solution, encoding="utf-8")
            (work / "test_solution.py").write_text(tests, encoding="utf-8")
            work.chmod(0o755)
            for f in work.iterdir():
                f.chmod(0o644)
            cmd = [
                "docker", "run", "--rm", "--name", name,
                "--network", "none",
                "--memory", MEMORY_LIMIT, "--memory-swap", MEMORY_LIMIT,
                "--cpus", "1", "--pids-limit", "64",
                "--user", "65534:65534",
                "--read-only", "--tmpfs", "/tmp:rw,size=16m",  # noqa: S108 - container tmpfs, not host
                "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
                "-v", f"{work}:/work:ro", "-w", "/work",
                "-e", "PYTHONDONTWRITEBYTECODE=1",
                self.image,
                "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_solution.py",
            ]  # fmt: skip
            try:
                proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
                    cmd, capture_output=True, text=True, timeout=self.time_limit_s
                )
            except subprocess.TimeoutExpired as exc:
                subprocess.run(["docker", "kill", name], capture_output=True)  # noqa: S603, S607
                partial = exc.stdout if isinstance(exc.stdout, str) else ""
                return RunResult(False, partial + f"\nKilled after {self.time_limit_s}s", True)
            if proc.returncode == 125 or any(m in proc.stderr for m in DAEMON_DOWN_MARKERS):
                # docker itself failed (image missing, daemon down): not a test result
                raise SandboxUnavailable(proc.stderr.strip()[-500:])
            out = (proc.stdout + proc.stderr).strip()
            if proc.returncode == 137:
                out += "\nKilled: memory limit (512 MB) exceeded"
            return RunResult(proc.returncode == 0, out)
