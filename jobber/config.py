"""
Simple config loader/merger for jobber.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
import subprocess
import json as jsonlib
import re


def load_config(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    text = p.read_text()
    if p.suffix.lower() in {".yaml", ".yml"}:
        raw = yaml.safe_load(text) or {}
        return normalize_keys(raw)
    if p.suffix.lower() == ".json":
        raw = json.loads(text)
        return normalize_keys(raw)
    # Try YAML as default
    raw = yaml.safe_load(text) or {}
    return normalize_keys(raw)


def merge_defaults(args: dict, defaults: Dict[str, Any]) -> dict:
    merged = dict(args)
    for k, v in defaults.items():
        if k not in merged or merged.get(k) is None:
            merged[k] = v
    return merged


def guess_aws_region() -> Optional[str]:
    try:
        out = subprocess.check_output(["aws", "configure", "get", "region"], stderr=subprocess.DEVNULL)
        region = out.decode().strip()
        return region or None
    except Exception:
        return None


def guess_aws_account() -> Optional[str]:
    try:
        out = subprocess.check_output(["aws", "sts", "get-caller-identity", "--output", "json"], stderr=subprocess.DEVNULL)
        data = jsonlib.loads(out.decode())
        return data.get("Account")
    except Exception:
        return None


def normalize_keys(obj: Any) -> Any:
    """
    Recursively convert dict keys with dashes to underscores to align with argparse dest names.
    """
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            nk = k.replace("-", "_")
            new[nk] = normalize_keys(v)
        return new
    if isinstance(obj, list):
        return [normalize_keys(x) for x in obj]
    return obj


def resolve_provider(conf: Dict[str, Any], default: str = "aws") -> str:
    """
    Extract a normalized provider string. Defaults to 'aws' unless overridden.
    """
    provider = (conf.get("provider") or default).lower()
    if provider not in {"aws", "gcp"}:
        raise ValueError(f"Unsupported provider: {provider}")
    return provider
