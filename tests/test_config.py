from pathlib import Path
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
