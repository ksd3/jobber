"""
Minimal docker build/push utilities for jobber.
"""

import subprocess
from dataclasses import dataclass
from typing import Optional


def run(cmd: list[str]) -> None:
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


@dataclass
class DockerImage:
    name: str
    tag: str = "latest"

    @property
    def ref(self) -> str:
        return f"{self.name}:{self.tag}"


def build_image(image: DockerImage, context: str = ".", dockerfile: Optional[str] = None) -> None:
    cmd = ["docker", "build", "-t", image.ref]
    if dockerfile:
        cmd += ["-f", dockerfile]
    cmd.append(context)
    run(cmd)


def tag_image(source: DockerImage, target_ref: str) -> None:
    run(["docker", "tag", source.ref, target_ref])


def push_image(ref: str) -> None:
    run(["docker", "push", ref])
