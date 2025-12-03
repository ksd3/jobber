"""
Minimal Vertex AI CustomJob submit helper for jobber.
"""

import subprocess
import time
from typing import Dict, List, Optional

from google.cloud import aiplatform_v1

from jobber import gcp_storage


def submit_job(
    project: str,
    region: str,
    image_uri: str,
    bucket: str,
    prefix: str,
    entry_point: Optional[str],
    source_dir: Optional[str],
    args: Dict[str, str],
    machine_type: str,
    accelerator_type: Optional[str] = None,
    accelerator_count: Optional[int] = None,
    replica_count: int = 1,
    job_name: Optional[str] = None,
    service_account: Optional[str] = None,
    network: Optional[str] = None,
    subnet: Optional[str] = None,
    ensure_data: bool = False,
    tail_logs: bool = False,
) -> str:
    if ensure_data:
        gcp_storage.upload_placeholder(bucket, prefix)

    job_display_name = job_name or "jobber"
    # Map hyperparameters to args list
    arg_list: List[str] = []
    for k, v in args.items():
        arg_list.extend([f"--{k}", str(v)])

    container_spec = {
        "image_uri": image_uri,
        "args": arg_list,
    }
    if entry_point:
        container_spec["command"] = ["python", entry_point]

    worker_pool_spec = {
        "machine_spec": {"machine_type": machine_type},
        "replica_count": replica_count,
        "container_spec": container_spec,
    }
    if accelerator_type and accelerator_count:
        worker_pool_spec["machine_spec"]["accelerator_type"] = accelerator_type
        worker_pool_spec["machine_spec"]["accelerator_count"] = accelerator_count

    custom_job = {
        "display_name": job_display_name,
        "job_spec": {
            "worker_pool_specs": [worker_pool_spec],
            "base_output_directory": {"output_uri_prefix": f"gs://{bucket}/{prefix}/outputs"},
        },
    }
    if service_account:
        custom_job["job_spec"]["service_account"] = service_account
    if network:
        custom_job["job_spec"]["network"] = network
    if subnet:
        custom_job["job_spec"]["subnetwork"] = subnet

    client = aiplatform_v1.JobServiceClient(client_options={"api_endpoint": f"{region}-aiplatform.googleapis.com"})
    parent = client.common_location_path(project, region)
    resp = client.create_custom_job(parent=parent, custom_job=custom_job)
    name = resp.name  # projects/.../locations/.../customJobs/...
    if tail_logs:
        _stream_job_logs(project, region, name, client)
    return name


def _stream_job_logs(project: str, region: str, job_name: str, client: aiplatform_v1.JobServiceClient, poll: int = 10) -> None:
    """
    Stream logs via gcloud; also poll job status and terminate the log stream when the job is terminal.
    """
    proc: subprocess.Popen | None = None
    try:
        cmd = ["gcloud", "ai", "custom-jobs", "stream-logs", job_name, f"--project={project}", f"--region={region}"]
        print(f"+ {' '.join(cmd)}")
        proc = subprocess.Popen(cmd)
    except FileNotFoundError:
        proc = None
    try:
        _wait_for_job_terminal(client, job_name, poll=poll)
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def _wait_for_job_terminal(client: aiplatform_v1.JobServiceClient, job_name: str, poll: int = 10) -> None:
    terminal = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_PAUSED"}
    last_state = None
    start = time.time()
    while True:
        job = client.get_custom_job(name=job_name)
        state = aiplatform_v1.JobState(job.state).name if job.state is not None else "UNKNOWN"
        if state != last_state:
            elapsed = int(time.time() - start)
            print(f"[{elapsed:>4}s] state={state}")
            last_state = state
        if state in terminal:
            if state != "JOB_STATE_SUCCEEDED":
                raise RuntimeError(f"Vertex job failed with state: {state}")
            return
        time.sleep(poll)
