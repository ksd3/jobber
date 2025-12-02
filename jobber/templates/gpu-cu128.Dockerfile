FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip

RUN python3 -m pip install torch torchvision

RUN python3 -m pip install sagemaker-training

CMD ["bash", "-c", "nvidia-smi && python3 -c 'import torch, torchvision; print(torch.__version__, torchvision.__version__)'"]

