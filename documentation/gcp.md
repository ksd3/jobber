# GCP Usage (Artifact Registry + Vertex AI)

## Prerequisites
- Enable Artifact Registry and Vertex AI APIs in your project.
- Roles: Artifact Registry Writer/Administrator for push, Storage Admin (or write) on your GCS bucket, Vertex AI Admin (or CustomJob Writer), and Service Account User if using a custom service account.
- Auth: `gcloud auth login` and `gcloud auth configure-docker <region>-docker.pkg.dev`.
- Python deps: `google-cloud-aiplatform` installed.

## Config (provider: gcp)
```yaml
provider: gcp

build:
  image: my-training
  tag: latest
  template: gpu-cu121
  context: .

push:
  image: my-training
  tag: latest
  project: my-gcp-project
  artifact-repo: my-repo
  region: us-central1

submit:
  image-uri: us-central1-docker.pkg.dev/my-gcp-project/my-repo/my-training:latest
  project: my-gcp-project
  gcs-bucket: my-bucket
  gcs-prefix: jobber-run
  region: us-central1
  entry-point: train.py
  source-dir: code-bundle
  machine-type: n1-standard-4
  accelerator-type: NVIDIA_TESLA_T4  # optional
  accelerator-count: 1                # optional
  replica-count: 1
  params:
    epochs: "5"
    batch-size: "64"
```

## Push to Artifact Registry
```bash
jobber push --provider gcp \
  --image my-training --tag latest \
  --project my-gcp-project --artifact-repo my-repo --region us-central1
```

## Sync data to GCS
```bash
jobber sync-data --provider gcp \
  --src ./mnist_data --dest gs://my-bucket/jobber-run/data --region us-central1
```

## Submit a Vertex AI Custom Job
```bash
jobber submit --provider gcp \
  --project my-gcp-project --region us-central1 \
  --image-uri us-central1-docker.pkg.dev/my-gcp-project/my-repo/my-training:latest \
  --gcs-bucket my-bucket --gcs-prefix jobber-run \
  --entry-point train.py --source-dir code-bundle \
  --param epochs=5 --param batch-size=64 \
  --machine-type n1-standard-4 \
  --tail-logs
```

## Notes
- Data path: Vertex job pulls from `gs://<bucket>/<prefix>/data/`; outputs land under `gs://<bucket>/<prefix>/outputs/`.
- `ensure_data` seeds `.../data/placeholder.txt` if empty (GCS).
- Logs: `--tail-logs` polls job state; you can also use `gcloud ai custom-jobs stream-logs <job-id>`.
