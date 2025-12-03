"""
Minimal GCS helpers for jobber.
"""

import subprocess
from pathlib import Path
from typing import Optional


def ensure_bucket(bucket: str, region: Optional[str] = None) -> None:
    """
    Ensure a GCS bucket exists. Uses gsutil to create if missing.
    """
    check_cmd = ["gsutil", "ls", f"gs://{bucket}"]
    try:
        run(check_cmd)
        return
    except subprocess.CalledProcessError:
        pass

    mb_cmd = ["gsutil", "mb"]
    if region:
        mb_cmd += ["-l", region]
    mb_cmd.append(f"gs://{bucket}")
    run(mb_cmd)


def sync_local_to_gcs(src: Path, dest_gs: str) -> None:
    """
    Sync a local folder to GCS (dest_gs should be gs://...).
    """
    cmd = ["gsutil", "-m", "rsync", "-r", str(src), dest_gs]
    run(cmd)


def upload_placeholder(bucket: str, prefix: str) -> None:
    """
    Upload a small placeholder file to prefix/data/placeholder.txt.
    """
    key = f"gs://{bucket}/{prefix.rstrip('/')}/data/placeholder.txt"
    cmd = ["gsutil", "cp", "-", key]
    run(cmd, input=b"placeholder")


def run(cmd: list[str], input: bytes | None = None) -> None:
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, input=input)
