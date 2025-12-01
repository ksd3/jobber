# Troubleshooting

- **No S3 objects found under …/data**: Upload at least one file to `s3://<bucket>/<prefix>/data/` (use `jobber sync-data` or rely on `ensure_data`).
- **Unrecognized arguments**: Hyperparameter names must match your argparse flags. Make argparse accept both dashes/underscores or align config `params` keys.
- **ROLE required**: Ensure `role-arn` is set via config or CLI; reinstall after config changes if tests fail to import.
- **Docker build hash/SSL errors on torch wheels**: Retry build; network blips can corrupt large downloads. Consider CPU template if GPUs aren’t needed.
- **Can’t tag/push image**: Build first (`jobber build`), then `jobber push`. Ensure Docker permissions and ECR repo perms.
- **Logs show CUDA not available**: You’re on a CPU instance type (e.g., m5). Use a GPU type (e.g., g5.xlarge) if you need GPUs.
- **Data download in script**: Your script may download MNIST if internet is allowed; otherwise, pre-upload data to S3 and read from `/opt/ml/input/data/train`.
- **Prefix mismatch**: Ensure `submit.prefix` matches where your data lives; SageMaker checks `s3://bucket/prefix/data/`.
- **Role S3 access**: Execution role must have `s3:ListBucket` on the bucket and `s3:GetObject/PutObject` on `prefix/*`.
- **Imports missing in container**: Add to `requirements.txt` or bake into the image; rebuild and push.
- **ECR auth issues**: Make sure you’ve run `jobber push` (which logs in) or `aws ecr get-login-password` manually; ensure region/account match.
