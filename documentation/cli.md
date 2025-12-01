# CLI Commands

All commands accept `--config` to load defaults from a YAML/JSON file.

## init
Create a sample config:
```bash
jobber init --path jobber.yml --region us-east-1 --role-arn arn:aws:iam::<acct>:role/SageMakerExecutionRole
```

## build
Build a Docker image (optionally render a template):
```bash
jobber build --image my-training --tag latest --template gpu-cu121 --context .
```
Flags: `--dockerfile` (custom file), `--template` (writes Dockerfile then builds).

## push
Push a local image to ECR (ensures repo, logs in, tags, pushes):
```bash
jobber push --image my-training --repo my-training --tag latest --region us-east-1
```

## submit
Submit a SageMaker training job:
```bash
jobber submit \
  --image-uri <acct>.dkr.ecr.us-east-1.amazonaws.com/my-training:latest \
  --role-arn arn:aws:iam::<acct>:role/SageMakerExecutionRole \
  --bucket your-bucket --prefix custom-run \
  --entry-point train.py --source-dir code-bundle \
  --param epochs=5 --param batch-size=64 \
  --tail-logs
```
Defaults from config fill missing args; `params` in config merge with CLI `--param`.
`ensure_data` is on by default; use `--no-ensure-data` to skip placeholder upload.

## templates
Manage Dockerfile templates:
```bash
jobber templates list
jobber templates show gpu-cu121
jobber templates add custom /path/to/Dockerfile
jobber templates delete custom
```

## sync-data
Sync a local folder to S3 (creates bucket if missing):
```bash
jobber sync-data --src ./mnist_data --dest s3://bucket/prefix/data --region us-east-1
```

## Examples with config
- Build from config:
  ```bash
  jobber build --config jobber.yml
  ```
- Push from config:
  ```bash
  jobber push --config jobber.yml
  ```
- Submit with config params + extra override:
  ```bash
  jobber submit --config jobber.yml --param epochs=10 --tail-logs
  ```
