"""
Minimal SageMaker submit helper for jobber (custom image).
"""

from typing import Dict, Optional

import boto3
from sagemaker.estimator import Estimator
from sagemaker.session import Session


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
) -> str:
    boto_session = boto3.Session(region_name=region) if region else boto3.Session()
    session = Session(boto_session=boto_session)
    if ensure_data:
        _ensure_placeholder_data(boto_session, bucket, prefix)
    estimator = Estimator(
        image_uri=image_uri,
        role=role_arn,
        instance_type=instance_type,
        instance_count=instance_count,
        hyperparameters=hyperparameters,
        output_path=f"s3://{bucket}/{prefix}/outputs",
        code_location=f"s3://{bucket}/{prefix}/code",
        sagemaker_session=session,
        entry_point=entry_point,
        source_dir=source_dir,
    )
    train_s3_path = f"s3://{bucket}/{prefix}/data"
    estimator.fit({"train": train_s3_path}, job_name=job_name, wait=not tail_logs)
    if tail_logs:
        session.logs_for_job(job_name=estimator.latest_training_job.name, wait=True, log_type="All")
    return estimator.latest_training_job.name


def _ensure_placeholder_data(boto_session, bucket: str, prefix: str) -> None:
    s3 = boto_session.client("s3")
    key_prefix = f"{prefix.rstrip('/')}/data/"
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=key_prefix, MaxKeys=1)
    if resp.get("KeyCount", 0) == 0:
        dummy_key = key_prefix + "placeholder.txt"
        s3.put_object(Bucket=bucket, Key=dummy_key, Body=b"placeholder")
