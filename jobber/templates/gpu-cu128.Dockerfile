FROM nvidia/cuda:12.8.0-cudnn8-runtime-ubuntu22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-dev \
    libjpeg-dev zlib1g-dev build-essential && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir 'numpy<2' && \
    python3 -m pip install --no-cache-dir \
      --retries 5 --timeout 300 \
      torch==2.2.0+cu128 torchvision==0.17.0+cu128 \
      --index-url https://download.pytorch.org/whl/cu128 && \
    python3 -m pip install --no-cache-dir -r requirements.txt && \
    python3 -m pip install --no-cache-dir 'sagemaker-training>=5'
COPY . .
ENTRYPOINT []
CMD []
