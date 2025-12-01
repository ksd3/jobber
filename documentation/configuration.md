# Configuration (`jobber.yml`)

You can keep defaults in a YAML/JSON config and avoid long CLI flags. Keys are read per subcommand (`build`, `push`, `submit`). Dashes in keys are normalized to underscores internally, so `batch-size` becomes `batch_size` when passed to your script (make argparse accept both).

## Example
```yaml
build:
  image: my-training
  tag: latest
  template: gpu-cu121
  context: .

push:
  image: my-training
  repo: my-training
  tag: latest
  region: us-east-1

submit:
  image-uri: <acct>.dkr.ecr.us-east-1.amazonaws.com/my-training:latest
  role-arn: arn:aws:iam::<acct>:role/SageMakerExecutionRole
  bucket: your-bucket
  prefix: custom-run
  region: us-east-1
  entry-point: train.py
  source-dir: code-bundle
  instance-type: ml.m5.xlarge
  instance-count: 1
  params:
    epochs: "5"
    batch-size: "64"
```

## Precedence
- CLI flags override config values.
- `params` in config provide default hyperparameters; CLI `--param KEY=VALUE` adds/overrides.
- `ensure_data` defaults to true; use `--no-ensure-data` to disable.

## AWS hints
- `jobber init` will try to guess region from `aws configure get region`.
- You still need a valid execution role ARN in the config or CLI.

## Data prefix
- Code assumes the `train` channel is `s3://<bucket>/<prefix>/data/`. Upload real data there or rely on `ensure_data` to drop a placeholder.

## Putting params in config vs CLI
- Config `params` are a base set. Example:
  ```yaml
  submit:
    params:
      epochs: "3"
      batch-size: "32"
  ```
- CLI `--param epochs=5` will override the config value for `epochs`.

## Minimal config stub
```yaml
submit:
  image-uri: ...
  role-arn: ...
  bucket: ...
  prefix: ...
```
Everything else can be supplied via CLI if you prefer.
