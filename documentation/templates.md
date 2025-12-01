# Dockerfile Templates

Jobber ships file-based templates under `jobber/templates/`. Included:
- `cpu.Dockerfile` (python:3.10-slim)
- `gpu-cu121.Dockerfile` (CUDA 12.1 runtime, PyTorch cu121)

Templates are packaged and can be managed via CLI.

## Use a template
```bash
jobber build --image my-training --template gpu-cu121
```
This writes `Dockerfile` from the template and builds the image.

## Manage templates
```bash
jobber templates list
jobber templates show gpu-cu121
jobber templates add my-custom /path/to/Dockerfile
jobber templates delete my-custom
```

Templates are stored as `*.Dockerfile` under `jobber/templates/`.

## Add your own template
- Create a Dockerfile tuned to your needs (e.g., different torch/CUDA).
- Add it:
  ```bash
  jobber templates add gpu-cu128 /path/to/cu128.Dockerfile
  ```
- Then build:
  ```bash
  jobber build --image my-training --template gpu-cu128
  ```
