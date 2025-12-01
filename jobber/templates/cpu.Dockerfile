FROM python:3.10-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev build-essential libjpeg-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt && \
    python3 -m pip install --no-cache-dir 'sagemaker-training>=5' && \
    python3 -m pip install --no-cache-dir 'numpy<2'
COPY . .
ENTRYPOINT []
CMD []
