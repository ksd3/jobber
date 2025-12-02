"""
Minimal SageMaker submit helper for jobber (custom image).
"""

import time
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError
from sagemaker.core.helper.session_helper import Session
from sagemaker.core.training.configs import (
    Compute,
    InputData,
    OutputDataConfig,
    SourceCode,
)
from sagemaker.core.shapes.shapes import StoppingCondition
from sagemaker.train import ModelTrainer


def submit_job(
    image_uri: str,
    role_arn: str,
    bucket: str,
    prefix: str,
    region: Optional[str],
    entry_point: Optional[str],
    source_dir: str,
    hyperparameters: Dict[str, str],
    instance_type: str,
    instance_count: int = 1,
    job_name: Optional[str] = None,
    tail_logs: bool = False,
    ensure_data: bool = False,
    use_spot: bool = False,
    max_wait_seconds: Optional[int] = None,
) -> str:
    boto_session = boto3.Session(region_name=region) if region else boto3.Session()
    session = Session(boto_session=boto_session)
    _ensure_bucket_exists(boto_session, bucket)
    if ensure_data:
        _ensure_placeholder_data(boto_session, bucket, prefix)

    source_code = SourceCode(source_dir=source_dir, entry_script=entry_point) if source_dir else None
    trainer = ModelTrainer(
        sagemaker_session=session,
        role=role_arn,
        training_image=image_uri,
        source_code=source_code,
        compute=Compute(
            instance_type=instance_type,
            instance_count=instance_count,
            enable_managed_spot_training=use_spot,
        ),
        stopping_condition=StoppingCondition(max_wait_time_in_seconds=max_wait_seconds)
        if max_wait_seconds is not None
        else None,
        output_data_config=OutputDataConfig(s3_output_path=f"s3://{bucket}/{prefix}/outputs"),
        base_job_name=job_name or "jobber",
        hyperparameters=hyperparameters or {},
    )

    train_input = InputData(channel_name="train", data_source=f"s3://{bucket}/{prefix}/data")
    if tail_logs:
        trainer.train(input_data_config=[train_input], wait=False, logs=False)
        job_name = trainer._latest_training_job.training_job_name
        _stream_training_logs(job_name, boto_session, poll=5)
    else:
        trainer.train(input_data_config=[train_input], wait=True, logs=False)
    return trainer._latest_training_job.training_job_name


def _ensure_bucket_exists(boto_session, bucket: str) -> None:
    s3 = boto_session.client("s3")
    try:
        s3.head_bucket(Bucket=bucket)
        return
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
    params = {"Bucket": bucket}
    region_name = s3.meta.region_name
    if region_name and region_name != "us-east-1":
        params["CreateBucketConfiguration"] = {"LocationConstraint": region_name}
    s3.create_bucket(**params)


def _ensure_placeholder_data(boto_session, bucket: str, prefix: str) -> None:
    s3 = boto_session.client("s3")
    key_prefix = f"{prefix.rstrip('/')}/data/"
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=key_prefix, MaxKeys=1)
    if resp.get("KeyCount", 0) == 0:
        dummy_key = key_prefix + "placeholder.txt"
        s3.put_object(Bucket=bucket, Key=dummy_key, Body=b"placeholder")


def _stream_training_logs(job_name: str, boto_session, poll: int = 5) -> None:
    """
    Stream CloudWatch logs for the training job until it finishes, with status updates.
    """
    logs_client = boto_session.client("logs")
    sm_client = boto_session.client("sagemaker")
    group = "/aws/sagemaker/TrainingJobs"
    next_tokens: dict[str, str] = {}
    terminal = {"Completed", "Failed", "Stopped"}
    start = time.time()
    first_log_at: float | None = None
    last_status = None
    last_secondary = None
    last_message = None
    last_wait_msg = 0.0

    while True:
        desc = sm_client.describe_training_job(TrainingJobName=job_name)
        status = desc["TrainingJobStatus"]
        secondary = desc.get("SecondaryStatus")
        transitions = desc.get("SecondaryStatusTransitions") or []
        message = transitions[0].get("StatusMessage") if transitions else None
        elapsed = int(time.time() - start)

        if status != last_status or secondary != last_secondary or message != last_message:
            sec = f" secondary={secondary}" if secondary else ""
            msg = f" message={message!r}" if message else ""
            print(f"[{elapsed:>4}s] status={status}{sec}{msg}")
            last_status, last_secondary, last_message = status, secondary, message

        # Pull logs from any available streams
        try:
            streams = logs_client.describe_log_streams(
                logGroupName=group, logStreamNamePrefix=f"{job_name}/", orderBy="LogStreamName"
            ).get("logStreams", [])
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
                raise
            streams = []

        if not streams and time.time() - last_wait_msg >= poll:
            # Do not print extra waiting lines; rely on status/secondary/message updates.
            last_wait_msg = time.time()

        for stream in streams:
            name = stream["logStreamName"]
            params = {
                "logGroupName": group,
                "logStreamName": name,
                "startFromHead": True,
            }
            if name in next_tokens:
                params["nextToken"] = next_tokens[name]
            resp = logs_client.get_log_events(**params)
            next_tokens[name] = resp["nextForwardToken"]
            for event in resp.get("events", []):
                if first_log_at is None:
                    first_log_at = time.time()
                    waited = int(first_log_at - start)
                    print(f"[{waited:>4}s] first logs available")
                print(f"{name}: {event['message']}")

        if status in terminal:
            if status == "Failed":
                reason = desc.get("FailureReason")
                raise RuntimeError(f"Training job failed: {reason}")
            return
        time.sleep(poll)
