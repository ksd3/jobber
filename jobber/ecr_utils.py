"""
Minimal ECR helpers for jobber.
"""

import boto3
from botocore.exceptions import ClientError
from dataclasses import dataclass


@dataclass
class ECRInfo:
    account_id: str
    region: str
    repo_name: str
    image_tag: str = "latest"

    @property
    def registry(self) -> str:
        return f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com"

    @property
    def image_uri(self) -> str:
        return f"{self.registry}/{self.repo_name}:{self.image_tag}"


def ensure_repo(ecr_client, repo_name: str) -> None:
    try:
        ecr_client.describe_repositories(repositoryNames=[repo_name])
    except ClientError as e:
        if e.response["Error"]["Code"] == "RepositoryNotFoundException":
            ecr_client.create_repository(repositoryName=repo_name)
        else:
            raise


def ecr_login(info: ECRInfo) -> None:
    import subprocess

    cmd = [
        "bash",
        "-lc",
        f"aws ecr get-login-password --region {info.region} | "
        f"docker login --username AWS --password-stdin {info.registry}",
    ]
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

