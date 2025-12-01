# SageMaker Behavior

## Channels and paths
- Jobber sets the `train` channel to `s3://<bucket>/<prefix>/data/`.
- SageMaker stages that prefix onto the container at `/opt/ml/input/data/train` before running your script.
- Model artifacts: anything under `/opt/ml/model` is tarred as `model.tar.gz` to `s3://<bucket>/<prefix>/outputs/<job>/output/`.

## Code upload
- `source_dir` is uploaded and extracted; `entry_point` is executed inside the container with hyperparameters as CLI args.
- Logs: stdout/stderr go to CloudWatch under `/aws/sagemaker/TrainingJobs/<job-name>`.

## Hyperparameters
- Config `params` and CLI `--param` become CLI args to your script. Dashes in config keys are normalized to underscores; make your argparse accept both if needed.

## Distributed/Instance types
- Instance types/count come from config/CLI. Multi-node/gpu require DDP setup in your code. Images use empty ENTRYPOINT to allow script mode.

## ensure_data
- Enabled by default; uploads `prefix/data/placeholder.txt` if empty to satisfy SageMaker’s input validation. Disable with `--no-ensure-data`.

## Data without internet
- If training containers lack egress, upload your dataset to `prefix/data/` (e.g., via `jobber sync-data`). Your script should read from `/opt/ml/input/data/train`.

## Outputs
- Model artifacts: `s3://<bucket>/<prefix>/outputs/<job>/output/model.tar.gz`.
- Code bundle: `s3://<bucket>/<prefix>/code/` (for reference).

## Typical flow in a training job
- SageMaker downloads the image from ECR to the training instance.
- It syncs the `train` channel from S3 to `/opt/ml/input/data/train`.
- It unpacks your `source_dir`, and runs `python entry_point` with hyperparameters as CLI args.
- Your script trains, writes models to `/opt/ml/model`, logs to stdout.
- SageMaker uploads `/opt/ml/model` to `output_path` as `model.tar.gz`.

## Hyperparameter name tips
- If your argparse uses `--batch-size`, consider also accepting `--batch_size` to handle normalized keys.
- Example argparse snippet:
  ```python
  parser.add_argument("--batch-size", "--batch_size", dest="batch_size", type=int, default=64)
  ```

## Using a different prefix/bucket
- Set `submit.bucket` and `submit.prefix` in `jobber.yml`.
- Upload data to `s3://<bucket>/<prefix>/data/` (`jobber sync-data ...`).
- Run `jobber submit --config jobber.yml`.
