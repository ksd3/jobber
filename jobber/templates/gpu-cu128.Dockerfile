FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python-is-python3

RUN python3 -m pip install torch torchvision

RUN python3 -m pip install sagemaker-training


