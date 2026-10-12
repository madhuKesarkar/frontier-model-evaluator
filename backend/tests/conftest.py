"""Shared fixtures. Docker tests use FME_SANDBOX_IMAGE (default fme-sandbox:1)."""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from app.sandbox import DockerSandbox


def _docker_ready(image: str) -> bool:
    if shutil.which("docker") is None:
        return False
    cmd = ["docker", "image", "inspect", image]
    probe = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
    return probe.returncode == 0


@pytest.fixture(scope="session")
def sandbox() -> DockerSandbox:
    image = os.environ.get("FME_SANDBOX_IMAGE", "fme-sandbox:1")
    if not _docker_ready(image):
        if os.environ.get("FME_REQUIRE_DOCKER") == "1":
            pytest.fail(f"Docker sandbox image {image!r} is required but not available")
        hint = f"build it with: docker build -t {image} sandbox/"
        pytest.skip(f"Docker sandbox image {image!r} not available ({hint})")
    return DockerSandbox(image)
