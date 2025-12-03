"""
Artifact Registry helpers for GCP.
"""

import subprocess
from dataclasses import dataclass

from jobber.docker_utils import DockerImage, run as docker_run


@dataclass
class ArtifactRef:
    project: str
    region: str
    repo: str
    image: str
    tag: str = "latest"

    @property
    def registry(self) -> str:
        return f"{self.region}-docker.pkg.dev"

    @property
    def uri(self) -> str:
        return f"{self.registry}/{self.project}/{self.repo}/{self.image}:{self.tag}"


def configure_docker(region: str) -> None:
    """
    Ensure docker is authenticated against Artifact Registry for the region.
    """
    cmd = ["gcloud", "auth", "configure-docker", f"{region}-docker.pkg.dev", "--quiet"]
    subprocess.run(cmd, check=True)


def ensure_repo(project: str, region: str, repo: str, description: str | None = None) -> None:
    """
    Ensure an Artifact Registry repository exists. Creates it if missing.
    """
    describe = [
        "gcloud",
        "artifacts",
        "repositories",
        "describe",
        repo,
        f"--project={project}",
        f"--location={region}",
        "--quiet",
    ]
    try:
        subprocess.run(describe, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    except subprocess.CalledProcessError:
        pass

    create = [
        "gcloud",
        "artifacts",
        "repositories",
        "create",
        repo,
        "--repository-format=docker",
        f"--project={project}",
        f"--location={region}",
        "--quiet",
    ]
    if description:
        create.append(f"--description={description}")
    subprocess.run(create, check=True)


def push_image(local: DockerImage, target: ArtifactRef) -> None:
    """
    Tag and push a local image to Artifact Registry.
    """
    docker_run(["docker", "tag", local.ref, target.uri])
    docker_run(["docker", "push", target.uri])
