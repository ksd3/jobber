"""
jobber CLI: build/push/submit helpers.
"""

import argparse
import sys
from pathlib import Path

from jobber.docker_utils import DockerImage, build_image, push_image, tag_image
from jobber.ecr_utils import ECRInfo, ensure_repo, ecr_login
from jobber.sm_submit import submit_job
from jobber import docker_templates
from jobber import config as cfg
from jobber import s3_utils
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
    import boto3

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
    )
    print(f"Submitted training job: {job_name}")


def cmd_init(args: argparse.Namespace) -> None:
    region = args.region or cfg.guess_aws_region() or "us-east-1"
    sample = {
        "build": {
            "image": "my-training",
            "tag": "latest",
            "template": "gpu-cu121",
            "context": ".",
        },
        "push": {
            "image": "my-training",
            "repo": "my-training",
            "tag": "latest",
            "region": region,
        },
        "submit": {
            "image-uri": "ACCOUNT.dkr.ecr.REGION.amazonaws.com/my-training:latest",
            "role-arn": args.role_arn or "arn:aws:iam::<account-id>:role/SageMakerExecutionRole",
            "bucket": "your-bucket",
            "prefix": "jobber-run",
            "region": region,
            "entry-point": "train.py",
            "source-dir": "code-bundle",
            "instance-type": "ml.m5.xlarge",
            "instance-count": 1,
        },
    }
    Path(args.path).write_text(yaml.safe_dump(sample, sort_keys=False))
    print(f"Wrote sample config to {args.path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobber", description="Build/push/submit helper CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a sample config file.")
    p_init.add_argument("--path", default="jobber.yml", help="Where to write the config (default: jobber.yml).")
    p_init.add_argument("--region", help="AWS region (defaults from AWS CLI).")
    p_init.add_argument("--role-arn", help="SageMaker execution role ARN.")
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
    p_push.set_defaults(func=cmd_push)

    p_submit = sub.add_parser("submit", help="Submit a SageMaker training job.")
    p_submit.add_argument("--config", help="Path to config file (yaml/json) for defaults.")
    p_submit.add_argument("--image-uri", required=False, help="ECR image URI.")
    p_submit.add_argument("--role-arn", required=False, help="SageMaker execution role ARN.")
    p_submit.add_argument("--bucket", required=False, help="S3 bucket for outputs.")
    p_submit.add_argument("--prefix", default="jobber-run", help="S3 prefix for artifacts.")
    p_submit.add_argument("--region", help="AWS region (defaults to AWS CLI config).")
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
    p_submit.set_defaults(ensure_data=True)
    p_submit.set_defaults(func=cmd_submit)

    p_sync = sub.add_parser("sync-data", help="Sync a local folder to S3.")
    p_sync.add_argument("--src", required=True, help="Local folder path.")
    p_sync.add_argument("--dest", required=True, help="Destination S3 URI (e.g., s3://bucket/prefix/data).")
    p_sync.add_argument("--region", help="AWS region.")
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
    # Ensure bucket exists
    dest = args.dest
    if dest.startswith("s3://"):
        bucket = dest.split("/")[2]
        s3_utils.ensure_bucket(bucket, region=args.region)
    s3_utils.sync_local_to_s3(Path(args.src), args.dest, region=args.region)
    print(f"Synced {args.src} -> {args.dest}")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Apply config defaults if provided
    if getattr(args, "config", None):
        conf = cfg.load_config(args.config)
        defaults = conf.get(args.command, {})
        # Merge defaults only for keys present in args
        args_dict = vars(args)
        merged = cfg.merge_defaults(args_dict, defaults)
        args = argparse.Namespace(**merged)
    args.func(args)


if __name__ == "__main__":
    main()
