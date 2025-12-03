# Docker Notes

## Build context and .dockerignore
`.dockerignore` excludes venvs, data/, model/, .git, node_modules, etc., plus jobber/test files. Keep the context small; templates expect your code and `requirements.txt` to be present.

Current `.dockerignore` patterns (summary):
- venvs/envs: `.venv`, `venv`, `env`
- caches: `__pycache__/`, `.pytest_cache/`, `.ipynb_checkpoints/`
- data/artifacts: `data/`, `model/`
- vcs/node: `.git/`, `node_modules/`
- project extras: `code-bundle/`, `jobber/`, `tests/`, helper scripts/zips (`push_to_ecr.py`, `submit_custom_image.py`, `sagemaker-job-example.zip`)
- `*.pyc`

Recommendation: mirror similar ignores in `.gitignore` to avoid accidental commits of bulky artifacts.

## Templates vs custom Dockerfile
- Use `--template` to render a canned Dockerfile.
- Use `--dockerfile` to point at a custom file.
- You can add your own template via `jobber templates add`.

## Local smoke test
Build and run locally to catch packaging issues:
```bash
jobber build --image my-training --template gpu-cu121
docker run --rm -v "$(pwd):/app" my-training:latest \
  python train.py --data-dir ./data --epochs 1 --batch-size 4
```
Add `--gpus all` if you have GPU and NVIDIA Container Toolkit installed.

## Entrypoint
Images leave `ENTRYPOINT`/`CMD` empty so SageMaker can override with `entry_point` from Estimator/submit. If you bake code into the image and don’t upload `source_dir`, set your own entrypoint accordingly.

For Vertex AI, `entry_point` maps to `python entry_point` with hyperparameters as `--key value` args (same as SageMaker). Ensure your script accepts option-style args.

## Large wheels
CUDA images pull large torch/vision wheels; network issues can cause hash/SSL errors. Retry builds if transient. For CPU-only, use the `cpu` template.

## Switching CUDA versions
- Use the template closest to your target (e.g., `gpu-cu121`). You can add a custom template for cu128 by pointing at the PyTorch cu128 wheel index and matching CUDA base image.
- Match torch/vision versions to the CUDA tag (see PyTorch “Get started” page).

## Minimal CPU Dockerfile example
```dockerfile
FROM python:3.10-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev build-essential libjpeg-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt 'sagemaker-training>=5' 'numpy<2'
COPY . .
ENTRYPOINT []
CMD []
```

## Minimal GPU Dockerfile example (cu121)
```dockerfile
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-dev \
    libjpeg-dev zlib1g-dev build-essential && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir 'numpy<2' && \
    pip install --no-cache-dir \
      --retries 5 --timeout 300 \
      torch==2.2.0+cu121 torchvision==0.17.0+cu121 \
      --index-url https://download.pytorch.org/whl/cu121 && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir 'sagemaker-training>=5'
COPY . .
ENTRYPOINT []
CMD []
```
