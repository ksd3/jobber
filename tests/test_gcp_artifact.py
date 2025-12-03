import subprocess

import jobber.gcp_artifact as gcp_artifact
from jobber.gcp_artifact import ArtifactRef, configure_docker, push_image
from jobber.docker_utils import DockerImage


def test_artifact_ref_formatting():
    ref = ArtifactRef(project="proj", region="us-central1", repo="repo", image="img", tag="t")
    assert ref.registry == "us-central1-docker.pkg.dev"
    assert ref.uri == "us-central1-docker.pkg.dev/proj/repo/img:t"


def test_configure_docker(monkeypatch):
    calls = []

    def fake_run(cmd, check):
        calls.append((cmd, check))

    monkeypatch.setattr(subprocess, "run", fake_run)
    configure_docker("us-west1")
    assert calls[0][0][:3] == ["gcloud", "auth", "configure-docker"]
    assert "us-west1-docker.pkg.dev" in calls[0][0]
    assert calls[0][1] is True


def test_ensure_repo_exists(monkeypatch):
    calls = []

    def fake_run(cmd, check, stdout=None, stderr=None):
        calls.append(cmd)
        # describe succeeds
        if "describe" in cmd:
            return

    monkeypatch.setattr(subprocess, "run", fake_run)
    gcp_artifact.ensure_repo("proj", "us-central1", "repo")
    assert "describe" in calls[0]
    assert len(calls) == 1


def test_ensure_repo_creates(monkeypatch):
    calls = []

    def fake_run(cmd, check, stdout=None, stderr=None):
        calls.append(cmd)
        if "describe" in cmd:
            raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    gcp_artifact.ensure_repo("proj", "us-central1", "repo", description="d")
    assert "describe" in calls[0]
    assert "create" in calls[1]
    assert "--description=d" in calls[1]


def test_push_image(monkeypatch):
    calls = []

    def fake_run(cmd):
        calls.append(cmd)

    monkeypatch.setattr("jobber.gcp_artifact.docker_run", fake_run)
    local = DockerImage(name="local", tag="t")
    target = ArtifactRef(project="proj", region="us", repo="r", image="img", tag="t2")
    push_image(local, target)
    assert calls[0] == ["docker", "tag", "local:t", target.uri]
    assert calls[1] == ["docker", "push", target.uri]
