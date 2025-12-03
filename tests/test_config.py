from pathlib import Path
import pytest
import jobber.config as cfg


def test_load_config_yaml(tmp_path):
    p = tmp_path / "c.yml"
    p.write_text("build:\n  image: foo\nsubmit:\n  bucket: b")
    data = cfg.load_config(p)
    assert data["build"]["image"] == "foo"
    assert data["submit"]["bucket"] == "b"


def test_merge_defaults():
    args = {"a": 1, "b": None}
    defaults = {"b": 2, "c": 3}
    merged = cfg.merge_defaults(args, defaults)
    assert merged["a"] == 1
    assert merged["b"] == 2
    assert "c" in merged


def test_normalize_keys():
    data = {"image-uri": "uri", "nested": {"role-arn": "arn"}, "list": [{"entry-point": "train.py"}]}
    norm = cfg.normalize_keys(data)
    assert norm["image_uri"] == "uri"
    assert norm["nested"]["role_arn"] == "arn"
    assert norm["list"][0]["entry_point"] == "train.py"


def test_normalize_keys_gcp_fields():
    data = {
        "provider": "gcp",
        "push": {"project-id": "proj", "artifact-repo": "repo"},
        "submit": {"gcs-bucket": "b", "gcs-prefix": "p"},
    }
    norm = cfg.normalize_keys(data)
    assert norm["provider"] == "gcp"
    assert norm["push"]["project_id"] == "proj"
    assert norm["push"]["artifact_repo"] == "repo"
    assert norm["submit"]["gcs_bucket"] == "b"
    assert norm["submit"]["gcs_prefix"] == "p"


def test_resolve_provider():
    assert cfg.resolve_provider({"provider": "gcp"}) == "gcp"
    assert cfg.resolve_provider({}) == "aws"
    with pytest.raises(ValueError):
        cfg.resolve_provider({"provider": "azure"})
