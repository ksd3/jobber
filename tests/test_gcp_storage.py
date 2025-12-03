import subprocess
from pathlib import Path

from jobber import gcp_storage


def test_ensure_bucket_existing(monkeypatch):
    calls = []

    def fake_run(cmd, check=True, input=None):
        calls.append(cmd)
        if "ls" in cmd:
            return

    monkeypatch.setattr(subprocess, "run", fake_run)
    gcp_storage.ensure_bucket("my-bucket", region="us-central1")
    assert calls[0][:2] == ["gsutil", "ls"]
    assert "gs://my-bucket" in calls[0]
    # No mb since ls succeeded
    assert len(calls) == 1


def test_ensure_bucket_create(monkeypatch):
    calls = []

    def fake_run(cmd, check=True, input=None):
        calls.append(cmd)
        if "ls" in cmd:
            raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    gcp_storage.ensure_bucket("my-bucket", region="us-central1")
    assert calls[0][:2] == ["gsutil", "ls"]
    assert calls[1][:2] == ["gsutil", "mb"]
    assert "-l" in calls[1]


def test_sync_local_to_gcs(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, check=True, input=None):
        calls.append(cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    src = tmp_path / "data"
    src.mkdir()
    gcp_storage.sync_local_to_gcs(src, "gs://bucket/prefix")
    assert calls[0][:4] == ["gsutil", "-m", "rsync", "-r"]
    assert calls[0][-1] == "gs://bucket/prefix"


def test_upload_placeholder(monkeypatch):
    calls = []

    def fake_run(cmd, check=True, input=None):
        calls.append((cmd, input))

    monkeypatch.setattr(subprocess, "run", fake_run)
    gcp_storage.upload_placeholder("b", "p")
    cmd, data = calls[0]
    assert cmd[:2] == ["gsutil", "cp"]
    assert cmd[-1] == "gs://b/p/data/placeholder.txt"
    assert data == b"placeholder"
