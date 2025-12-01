import subprocess
import pytest

from jobber.docker_utils import DockerImage, build_image, tag_image, push_image


def test_docker_image_ref():
    img = DockerImage(name="myrepo/myimg", tag="v1")
    assert img.ref == "myrepo/myimg:v1"


def test_run_wrappers(monkeypatch):
    calls = []

    def fake_run(cmd, check):
        calls.append(cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    img = DockerImage(name="repo/img", tag="t")
    build_image(img, context=".", dockerfile="Dockerfile.test")
    tag_image(img, "target:tag")
    push_image("target:tag")

    assert calls[0][:3] == ["docker", "build", "-t"]
    assert calls[1] == ["docker", "tag", "repo/img:t", "target:tag"]
    assert calls[2] == ["docker", "push", "target:tag"]
