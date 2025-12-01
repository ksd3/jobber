"""
Minimal S3 utilities for jobber.
"""

import subprocess
from pathlib import Path
from typing import Optional


def sync_local_to_s3(src: Path, dest_s3: str, region: Optional[str] = None) -> None:
    cmd = ["aws", "s3", "sync", str(src), dest_s3]
    if region:
        cmd += ["--region", region]
    run(cmd)


def ensure_bucket(bucket: str, region: Optional[str] = None) -> None:
    cmd = ["aws", "s3api", "head-bucket", "--bucket", bucket]
    if region:
        cmd += ["--region", region]
    try:
        run(cmd)
    except subprocess.CalledProcessError:
        # Try to create the bucket
        cmd = ["aws", "s3api", "create-bucket", "--bucket", bucket]
        if region and region != "us-east-1":
            cmd += ["--create-bucket-configuration", f"LocationConstraint={region}"]
        if region:
            cmd += ["--region", region]
        run(cmd)


def upload_placeholder(bucket: str, prefix: str, region: Optional[str] = None) -> None:
    key = f"{prefix.rstrip('/')}/data/placeholder.txt"
    cmd = ["aws", "s3", "cp", "-", f"s3://{bucket}/{key}", "--quiet"]
    if region:
        cmd += ["--region", region]
    run(cmd, input=b"placeholder")


def run(cmd: list[str], input: bytes | None = None) -> None:
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, input=input)
