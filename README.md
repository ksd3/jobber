# Jobber Documentation

Jobber is a small helper to:
- Build Docker images (optionally from templates)
- Push images to ECR
- Submit SageMaker training jobs (with config-driven defaults)
- Sync local data to S3 and seed empty data prefixes

## Contents
- `configuration.md`: Config file format, merging, hyperparameters.
- `cli.md`: Command-by-command reference with examples.
- `templates.md`: Dockerfile templates (list/show/add/delete).
- `docker.md`: Building images, .dockerignore, local smoke tests.
- `sagemaker.md`: Channel paths, hyperparameters, outputs, ensure_data.
- `troubleshooting.md`: Common issues and fixes.

## Prerequisites
- Docker installed (and NVIDIA Container Toolkit if using GPU images).
- AWS CLI installed and configured (`aws configure`).
- Python 3.10+ with `pip install -e .` (or `uv pip install -e .`).
- SageMaker execution role ARN with S3/List/Get/Put and ECR pull permissions.
- For ECR push: IAM perms to create repo/login/push.

## Quickstart (no config)
```bash
# 1) Build (render a template)
jobber build --image my-training --template gpu-cu121

# 2) Push to ECR
jobber push --image my-training --repo my-training --region us-east-1

# 3) Submit a SageMaker job
jobber submit \
  --image-uri <acct>.dkr.ecr.us-east-1.amazonaws.com/my-training:latest \
  --role-arn arn:aws:iam::<acct>:role/SageMakerExecutionRole \
  --bucket your-bucket --prefix custom-run \
  --entry-point train.py --source-dir code-bundle \
  --param epochs=5 --param batch-size=64 \
  --tail-logs
```

## Quickstart (with config)
1) Create a config:
   ```bash
   jobber init --path jobber.yml --region us-east-1 --role-arn <role>
   ```
2) Edit `jobber.yml` (bucket/prefix/image-uri/params/etc.).
3) Run:
   ```bash
   jobber build --config jobber.yml
   jobber push  --config jobber.yml
   jobber submit --config jobber.yml --tail-logs
   ```

## Data upload
- Auto-placeholder: enabled by default (`ensure_data`), seeds `prefix/data/placeholder.txt` if empty.
- Upload real data:
  ```bash
  jobber sync-data --src ./mnist_data --dest s3://bucket/prefix/data --region us-east-1
  ```
