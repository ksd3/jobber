"""
jobber CLI: build/push/submit helpers.
"""

import argparse
import sys
from pathlib import Path

from jobber.docker_utils import DockerImage, build_image, push_image, tag_image
from jobber import docker_templates
from jobber import config as cfg
from jobber import gcp_storage
from jobber.gcp_artifact import ArtifactRef, configure_docker as gcp_auth, ensure_repo as gcp_ensure_repo, push_image as gcp_push
import yaml


def cmd_build(args: argparse.Namespace) -> None:
    context = args.context or "."
    tag = args.tag or "latest"
    dockerfile = args.dockerfile
    _ensure_default_dockerignore(context)
    if not args.image:
        print("Image name is required (e.g., --image my-training)", file=sys.stderr)
        sys.exit(1)
    if getattr(args, "template", None):
        tmpl = docker_templates.get_template(args.template)
        df_path = Path(context) / "Dockerfile"
        df_path.parent.mkdir(parents=True, exist_ok=True)
        df_path.write_text(tmpl.content)
        dockerfile = str(df_path)
        print(f"Wrote Dockerfile from template: {tmpl.name} -> {df_path}")
    image = DockerImage(name=args.image, tag=tag)
    build_image(image, context=context, dockerfile=dockerfile)
    print(f"Built {image.ref}")


def cmd_push(args: argparse.Namespace) -> None:
    provider = cfg.resolve_provider({"provider": args.provider})
    if not args.image:
        print("Image name is required (e.g., --image my-training)", file=sys.stderr)
        sys.exit(1)

    if provider == "aws":
        import boto3
        from jobber.ecr_utils import ECRInfo, ensure_repo, ecr_login

        session = boto3.Session(region_name=args.region) if args.region else boto3.Session()
        if not session.region_name:
            print("Region not set; pass --region or configure AWS CLI.", file=sys.stderr)
            sys.exit(1)
        account_id = session.client("sts").get_caller_identity()["Account"]
        info = ECRInfo(account_id=account_id, region=session.region_name, repo_name=args.repo, image_tag=args.tag)
        ensure_repo(session.client("ecr"), args.repo)
        ecr_login(info)
        src = DockerImage(name=args.image, tag=args.tag)
        tag_image(src, info.image_uri)
        push_image(info.image_uri)
        print(f"Pushed {info.image_uri}")
        return

    # GCP path
    if not args.project or not args.artifact_repo:
        print("GCP push requires --project and --artifact-repo", file=sys.stderr)
        sys.exit(1)
    if not args.region:
        print("GCP push requires --region for Artifact Registry", file=sys.stderr)
        sys.exit(1)
    ref = ArtifactRef(project=args.project, region=args.region, repo=args.artifact_repo, image=args.repo or args.image, tag=args.tag)
    gcp_ensure_repo(args.project, args.region, args.artifact_repo)
    gcp_auth(args.region)
    gcp_push(DockerImage(name=args.image, tag=args.tag), ref)
    print(f"Pushed {ref.uri}")


def cmd_submit(args: argparse.Namespace) -> None:
    extra_hps = {}
    # params from config
    if getattr(args, "params", None):
        extra_hps.update(args.params)
    for item in args.param:
        if "=" not in item:
            print(f"Invalid --param {item!r}; expected KEY=VALUE", file=sys.stderr)
            sys.exit(1)
        k, v = item.split("=", 1)
        extra_hps[k] = v
    provider = cfg.resolve_provider({"provider": args.provider})
    if provider == "gcp":
        try:
            from jobber import vertex_submit
        except ModuleNotFoundError as e:
            missing = getattr(e, "name", "") or str(e)
            if "google" in missing or "aiplatform" in missing or "vertex_submit" in missing:
                print(
                    "google-cloud-aiplatform not installed; install with `pip install google-cloud-aiplatform`.",
                    file=sys.stderr,
                )
                sys.exit(1)
            raise

        gcs_bucket = args.gcs_bucket or args.bucket
        gcs_prefix = args.gcs_prefix or args.prefix
        if not args.project or not args.region or not gcs_bucket or not gcs_prefix:
            print("GCP submit requires --project, --region, and GCS bucket/prefix (via --gcs-bucket/--gcs-prefix or --bucket/--prefix)", file=sys.stderr)
            sys.exit(1)
        job_name = vertex_submit.submit_job(
            project=args.project,
            region=args.region,
            image_uri=args.image_uri,
            bucket=gcs_bucket,
            prefix=gcs_prefix,
            entry_point=args.entry_point,
            source_dir=str(Path(args.source_dir).resolve()) if args.source_dir else None,
            args=extra_hps,
            machine_type=args.machine_type or "n1-standard-4",
            accelerator_type=args.accelerator_type,
            accelerator_count=args.accelerator_count,
            replica_count=args.replica_count or 1,
            job_name=args.job_name,
            service_account=args.service_account,
            network=args.network,
            subnet=args.subnet,
            ensure_data=getattr(args, "ensure_data", True),
            tail_logs=args.tail_logs,
        )
        print(f"Submitted Vertex AI job: {job_name}")
        return

    from jobber.sm_submit import submit_job

    job_name = submit_job(
        image_uri=args.image_uri,
        role_arn=args.role_arn,
        bucket=args.bucket,
        prefix=args.prefix,
        region=args.region,
        entry_point=args.entry_point,
        source_dir=str(Path(args.source_dir).resolve()),
        hyperparameters=extra_hps,
        instance_type=args.instance_type,
        instance_count=args.instance_count,
        job_name=args.job_name,
        tail_logs=args.tail_logs,
        ensure_data=getattr(args, "ensure_data", True),
        use_spot=args.use_spot,
        max_wait_seconds=args.max_wait_seconds,
    )
    print(f"Submitted training job: {job_name}")


def cmd_init(args: argparse.Namespace) -> None:
    def prompt(msg: str, default: str | None = None) -> str:
        suffix = f" [{default}]" if default is not None else ""
        val = input(f"{msg}{suffix}: ").strip()
        return val or (default if default is not None else "")

    def prompt_int(msg: str, default: int) -> int:
        val = prompt(msg, str(default))
        try:
            return int(val)
        except ValueError:
            return default

    def prompt_bool(msg: str, default: bool) -> bool:
        val = prompt(msg + " (y/n)", "y" if default else "n").lower()
        return val in {"y", "yes", "true", "1"}

    provider = args.provider or prompt("Provider (aws/gcp)", "")
    if not provider:
        print("Provider is required (aws or gcp).", file=sys.stderr)
        sys.exit(1)
    if provider == "aws":
        region = args.region or cfg.guess_aws_region() or "us-east-1"
        build_image = prompt("Build image name", "my-training")
        build_tag = prompt("Build tag", "latest")
        build_template = prompt("Docker template", "gpu-cu121")
        build_context = prompt("Build context", ".")

        push_repo = prompt("ECR repo name", build_image)
        push_region = prompt("AWS region", region)

        submit_image_uri = prompt(
            "Submit image URI",
            f"ACCOUNT.dkr.ecr.{push_region}.amazonaws.com/{push_repo}:{build_tag}",
        )
        role_arn = prompt("SageMaker role ARN", args.role_arn or "arn:aws:iam::<account-id>:role/SageMakerExecutionRole")
        bucket = prompt("S3 bucket", "your-bucket")
        prefix = prompt("S3 prefix", "jobber-run")
        entry_point = prompt("Entry point", "train.py")
        source_dir = prompt("Source dir", "code-bundle")
        instance_type = prompt("Instance type", "ml.m5.xlarge")
        instance_count = prompt_int("Instance count", 1)
        use_spot = prompt_bool("Use managed spot", False)
        max_wait = prompt_int("Max wait seconds (0 to skip)", 0)
        sample = {
            "provider": "aws",
            "build": {
                "image": build_image,
                "tag": build_tag,
                "template": build_template,
                "context": build_context,
            },
            "push": {
                "image": build_image,
                "repo": push_repo,
                "tag": build_tag,
                "region": push_region,
            },
            "submit": {
                "image-uri": submit_image_uri,
                "role-arn": role_arn,
                "bucket": bucket,
                "prefix": prefix,
                "region": push_region,
                "entry-point": entry_point,
                "source-dir": source_dir,
                "instance-type": instance_type,
                "instance-count": instance_count,
                "use-spot": use_spot,
                "max-wait-seconds": max_wait or None,
            },
        }
    else:
        region = args.region or "us-central1"
        build_image = prompt("Build image name", "my-training")
        build_tag = prompt("Build tag", "latest")
        build_template = prompt("Docker template", "gpu-cu128")
        build_context = prompt("Build context", "code-bundle")

        project = prompt("GCP project", "my-gcp-project")
        artifact_repo = prompt("Artifact Registry repo", "my-artifact-repo")
        push_region = prompt("Region", region)

        gcs_bucket = prompt("GCS bucket", "my-gcs-bucket")
        gcs_prefix = prompt("GCS prefix", "jobber-run")
        entry_point = prompt("Entry point", "train.py")
        source_dir = prompt("Source dir", "code-bundle")
        machine_type = prompt("Machine type", "a2-highgpu-1g")
        accel_type = prompt("Accelerator type", "NVIDIA_TESLA_A100")
        accel_count = prompt_int("Accelerator count", 1)
        replica_count = prompt_int("Replica count", 1)
        use_spot = prompt_bool("Use spot/preemptible", False)
        image_uri_default = f"{push_region}-docker.pkg.dev/{project}/{artifact_repo}/{build_image}:{build_tag}"
        image_uri = prompt("Submit image URI", image_uri_default)

        sample = {
            "provider": "gcp",
            "build": {
                "image": build_image,
                "tag": build_tag,
                "template": build_template,
                "context": build_context,
            },
            "push": {
                "image": build_image,
                "tag": build_tag,
                "project": project,
                "artifact-repo": artifact_repo,
                "region": push_region,
            },
            "submit": {
                "image-uri": image_uri,
                "project": project,
                "gcs-bucket": gcs_bucket,
                "gcs-prefix": gcs_prefix,
                "region": push_region,
                "entry-point": entry_point,
                "source-dir": source_dir,
                "machine-type": machine_type,
                "accelerator-type": accel_type,
                "accelerator-count": accel_count,
                "replica-count": replica_count,
                "use-spot": use_spot,
            },
        }
    Path(args.path).write_text(yaml.safe_dump(sample, sort_keys=False))
    print(f"Wrote sample config to {args.path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobber", description="Build/push/submit helper CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a sample config file.")
    p_init.add_argument("--path", default="jobber.yml", help="Where to write the config (default: jobber.yml).")
    p_init.add_argument("--region", help="Cloud region (AWS/GCP).")
    p_init.add_argument("--role-arn", help="SageMaker execution role ARN (AWS only).")
    p_init.add_argument("--provider", choices=["aws", "gcp"], default=None, help="Cloud provider for the sample config (prompts if omitted).")
    p_init.set_defaults(func=cmd_init)

    p_build = sub.add_parser("build", help="Build a Docker image.")
    p_build.add_argument("--config", help="Path to config file (yaml/json) for defaults.")
    p_build.add_argument("--image", required=False, help="Local image name (e.g., myimg).")
    p_build.add_argument("--tag", help="Image tag (default: latest).")
    p_build.add_argument("--dockerfile", help="Path to Dockerfile (default: ./Dockerfile).")
    p_build.add_argument("--context", help="Build context (default: current dir).")
    p_build.add_argument(
        "--template",
        choices=[t.name for t in docker_templates.list_templates()],
        help="Render a canned Dockerfile template to the current directory before building.",
    )
    p_build.set_defaults(func=cmd_build)

    p_tpl = sub.add_parser("templates", help="Manage Dockerfile templates.")
    tpl_sub = p_tpl.add_subparsers(dest="tpl_cmd", required=True)
    p_tpl_list = tpl_sub.add_parser("list", help="List templates.")
    p_tpl_list.set_defaults(func=lambda a: [print(t.name) for t in docker_templates.list_templates()])

    p_tpl_show = tpl_sub.add_parser("show", help="Show template content.")
    p_tpl_show.add_argument("name")
    p_tpl_show.set_defaults(func=lambda a: print(docker_templates.get_template(a.name).content))

    p_tpl_add = tpl_sub.add_parser("add", help="Add a custom template from a file.")
    p_tpl_add.add_argument("name")
    p_tpl_add.add_argument("source")
    p_tpl_add.set_defaults(func=lambda a: docker_templates.add_template(a.name, Path(a.source)))

    p_tpl_del = tpl_sub.add_parser("delete", help="Delete a template.")
    p_tpl_del.add_argument("name")
    p_tpl_del.set_defaults(func=lambda a: docker_templates.delete_template(a.name))

    p_push = sub.add_parser("push", help="Push local image to ECR.")
    p_push.add_argument("--config", help="Path to config file (yaml/json) for defaults.")
    p_push.add_argument("--image", required=False, help="Local image name to push (must be built).")
    p_push.add_argument("--repo", required=False, help="ECR repository name.")
    p_push.add_argument("--tag", default="latest", help="Tag (default: latest).")
    p_push.add_argument("--region", help="AWS region (defaults to AWS CLI config).")
    p_push.add_argument("--provider", choices=["aws", "gcp"], help="Target cloud (default: aws).")
    p_push.add_argument("--project", help="GCP project (Artifact Registry).")
    p_push.add_argument("--artifact-repo", dest="artifact_repo", help="GCP Artifact Registry repository name.")
    p_push.set_defaults(func=cmd_push)

    p_submit = sub.add_parser("submit", help="Submit a training job (SageMaker or Vertex AI).")
    p_submit.add_argument("--config", help="Path to config file (yaml/json) for defaults.")
    p_submit.add_argument("--image-uri", required=False, help="ECR image URI.")
    p_submit.add_argument("--role-arn", required=False, help="SageMaker execution role ARN.")
    p_submit.add_argument("--bucket", required=False, help="S3 bucket for outputs.")
    p_submit.add_argument("--prefix", default="jobber-run", help="S3/GCS prefix for artifacts.")
    p_submit.add_argument("--region", help="Cloud region (AWS or GCP).")
    p_submit.add_argument("--entry-point", help="Training script filename inside source_dir.")
    p_submit.add_argument("--source-dir", default="code-bundle", help="Directory to upload as source.")
    p_submit.add_argument("--instance-type", default="ml.m5.xlarge")
    p_submit.add_argument("--instance-count", type=int, default=1)
    p_submit.add_argument("--job-name", help="Optional training job name.")
    p_submit.add_argument("--param", action="append", default=[], metavar="KEY=VALUE", help="Hyperparameter (repeat).")
    p_submit.add_argument("--tail-logs", action="store_true", help="Stream CloudWatch logs.")
    p_submit.add_argument("--use-spot", action="store_true", help="Use SageMaker managed spot training.")
    p_submit.add_argument(
        "--max-wait-seconds",
        type=int,
        help="Max wait time for managed spot training (SageMaker StoppingCondition.MaxWaitTimeInSeconds).",
    )
    p_submit.add_argument(
        "--no-ensure-data",
        action="store_false",
        dest="ensure_data",
        help="Disable placeholder upload if the data prefix is empty (defaults to enabled).",
    )
    p_submit.add_argument("--provider", choices=["aws", "gcp"], help="Target cloud (default: aws).")
    # GCP-specific
    p_submit.add_argument("--project", help="GCP project for Vertex AI.")
    p_submit.add_argument("--gcs-bucket", dest="gcs_bucket", help="GCS bucket for data/outputs.")
    p_submit.add_argument("--gcs-prefix", dest="gcs_prefix", help="GCS prefix for data/outputs.")
    p_submit.add_argument("--machine-type", help="Vertex AI machine type (e.g., n1-standard-4).")
    p_submit.add_argument("--accelerator-type", help="Vertex AI accelerator type (e.g., NVIDIA_TESLA_T4).")
    p_submit.add_argument("--accelerator-count", type=int, help="Vertex AI accelerator count.")
    p_submit.add_argument("--replica-count", type=int, help="Vertex AI replica count.")
    p_submit.add_argument("--service-account", dest="service_account", help="Service account email for Vertex AI job.")
    p_submit.add_argument("--network", help="VPC network for Vertex AI job.")
    p_submit.add_argument("--subnet", help="VPC subnet for Vertex AI job.")
    p_submit.set_defaults(ensure_data=True)
    p_submit.set_defaults(func=cmd_submit)

    p_sync = sub.add_parser("sync-data", help="Sync a local folder to object storage.")
    p_sync.add_argument("--src", required=True, help="Local folder path.")
    p_sync.add_argument("--dest", required=True, help="Destination URI (s3://... or gs://...).")
    p_sync.add_argument("--region", help="Cloud region.")
    p_sync.add_argument("--provider", choices=["aws", "gcp"], help="Target cloud (default: inferred from dest or config).")
    p_sync.set_defaults(func=cmd_sync)

    return parser


def _ensure_default_dockerignore(context: str) -> None:
    """
    Create a minimal .dockerignore in the build context if one is missing.
    Keeps build contexts lean to avoid large/slow uploads.
    """
    path = Path(context) / ".dockerignore"
    if path.exists():
        return
    defaults = [
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "*.pyc",
        "*.pyo",
        "*.swp",
        "*.tmp",
        "sagemaker-python-sdk",
        "tests",
    ]
    path.write_text("\n".join(defaults) + "\n")


def cmd_sync(args: argparse.Namespace) -> None:
    dest = args.dest
    provider = cfg.resolve_provider({"provider": args.provider})

    if dest.startswith("gs://") or provider == "gcp":
        if not dest.startswith("gs://"):
            print("GCP sync requires gs:// destination", file=sys.stderr)
            sys.exit(1)
        parts = dest.split("/", 3)
        if len(parts) < 3 or not parts[2]:
            print("Invalid GCS URI; expected gs://bucket/prefix", file=sys.stderr)
            sys.exit(1)
        bucket = parts[2]
        gcp_storage.ensure_bucket(bucket, region=args.region)
        gcp_storage.sync_local_to_gcs(Path(args.src), dest)
        print(f"Synced {args.src} -> {dest}")
        return

    # AWS path
    if not dest.startswith("s3://"):
        print("Destination must start with s3:// for AWS sync", file=sys.stderr)
        sys.exit(1)
    from jobber import s3_utils

    bucket = dest.split("/")[2]
    s3_utils.ensure_bucket(bucket, region=args.region)
    s3_utils.sync_local_to_s3(Path(args.src), dest, region=args.region)
    print(f"Synced {args.src} -> {dest}")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Apply config defaults if provided
    if getattr(args, "config", None):
        conf = cfg.load_config(args.config)
        defaults = conf.get(args.command, {})
        # allow top-level provider to flow into command defaults
        if "provider" not in defaults and "provider" in conf:
            defaults = dict(defaults)
            defaults["provider"] = conf["provider"]
        # Merge defaults only for keys present in args
        args_dict = vars(args)
        merged = cfg.merge_defaults(args_dict, defaults)
        args = argparse.Namespace(**merged)
    args.func(args)


if __name__ == "__main__":
    main()
