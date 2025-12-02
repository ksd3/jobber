import types
import sys
from types import SimpleNamespace

import jobber.cli as cli
import jobber.config as cfg


def test_parser_subcommands():
    parser = cli.build_parser()
    args = parser.parse_args(["build", "--image", "i"])
    assert args.func == cli.cmd_build
    args = parser.parse_args(["push", "--image", "i", "--repo", "r"])
    assert args.func == cli.cmd_push
    args = parser.parse_args(
        [
            "submit",
            "--image-uri",
            "uri",
            "--role-arn",
            "arn",
            "--bucket",
            "b",
        ]
    )
    assert args.func == cli.cmd_submit


def test_cmd_build(monkeypatch):
    calls = {}

    def fake_build_image(image, context, dockerfile):
        calls["image"] = image
        calls["context"] = context
        calls["dockerfile"] = dockerfile

    monkeypatch.setattr(cli, "build_image", fake_build_image)

    args = SimpleNamespace(image="repo/img", tag="t", context=".", dockerfile=None, template=None)
    cli.cmd_build(args)
    assert calls["image"].ref == "repo/img:t"
    assert calls["context"] == "."


def test_cmd_build_template_respects_context(tmp_path, monkeypatch):
    calls = {}

    def fake_build_image(image, context, dockerfile):
        calls["context"] = context
        calls["dockerfile"] = dockerfile

    monkeypatch.setattr(cli, "build_image", fake_build_image)

    ctx = tmp_path / "code-bundle"
    ctx.mkdir()
    args = SimpleNamespace(image="repo/img", tag=None, context=str(ctx), dockerfile=None, template="cpu")
    cli.cmd_build(args)
    assert calls["context"] == str(ctx)
    assert calls["dockerfile"] == str(ctx / "Dockerfile")
    assert (ctx / "Dockerfile").exists()
    assert (ctx / ".dockerignore").exists()


def test_cmd_push(monkeypatch):
    calls = {}

    class FakeSession:
        def __init__(self, region_name=None):
            self.region_name = region_name or "us-east-1"

        def client(self, name):
            if name == "sts":
                return FakeSTS()
            if name == "ecr":
                return SimpleNamespace()
            raise ValueError(name)

    class FakeSTS:
        def get_caller_identity(self):
            return {"Account": "123"}

    def fake_ensure_repo(ecr_client, repo_name):
        calls["ensure_repo"] = repo_name

    def fake_ecr_login(info):
        calls["login"] = info.registry

    def fake_tag_image(src, target_ref):
        calls["tagged"] = target_ref

    def fake_push_image(ref):
        calls["pushed"] = ref

    monkeypatch.setattr(cli, "ECRInfo", cli.ECRInfo)
    monkeypatch.setattr(cli, "ensure_repo", fake_ensure_repo)
    monkeypatch.setattr(cli, "ecr_login", fake_ecr_login)
    monkeypatch.setattr(cli, "tag_image", fake_tag_image)
    monkeypatch.setattr(cli, "push_image", fake_push_image)
    monkeypatch.setattr(cli, "DockerImage", cli.DockerImage)

    # Patch boto3.Session used inside cmd_push
    import jobber.cli as cli_module

    def fake_session(region_name=None):
        return FakeSession(region_name)

    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(Session=fake_session))

    args = SimpleNamespace(image="local/img", repo="repo", tag="t", region="us-east-1")
    cli.cmd_push(args)
    assert calls["ensure_repo"] == "repo"
    assert calls["pushed"].endswith(":t")


def test_cmd_submit(monkeypatch):
    recorded = {}

    def fake_submit_job(**kwargs):
        recorded.update(kwargs)
        return "job-123"

    monkeypatch.setattr(cli, "submit_job", fake_submit_job)

    args = SimpleNamespace(
        image_uri="uri",
        role_arn="arn",
        bucket="b",
        prefix="p",
        region=None,
        entry_point="train.py",
        source_dir=".",
        instance_type="ml.m5.xlarge",
        instance_count=1,
        job_name=None,
        param=["epochs=5", "lr=0.1"],
        tail_logs=False,
    )
    cli.cmd_submit(args)
    assert recorded["image_uri"] == "uri"
    assert recorded["hyperparameters"] == {"epochs": "5", "lr": "0.1"}


def test_cli_config_defaults(tmp_path, monkeypatch):
    # Write config
    conf = tmp_path / "jobber.yml"
    conf.write_text(
        "submit:\n"
        "  image-uri: uri\n"
        "  role-arn: arn\n"
        "  bucket: b\n"
        "  prefix: p\n"
        "  region: us-east-1\n"
        "  entry-point: train.py\n"
        "  source-dir: code-bundle\n"
        "  instance-type: ml.m5.xlarge\n"
        "  instance-count: 1\n"
        "  params:\n"
        "    foo: bar\n"
    )

    recorded = {}

    def fake_submit_job(**kwargs):
        recorded.update(kwargs)
        return "job-xyz"

    monkeypatch.setattr(cli, "submit_job", fake_submit_job)

    argv = [
        "submit",
        "--config",
        str(conf),
        "--param",
        "epochs=1",
        "--image-uri",
        "uri",
        "--role-arn",
        "arn",
        "--bucket",
        "b",
    ]
    cli.main(argv)
    assert recorded["image_uri"] == "uri"
    assert recorded["role_arn"] == "arn"
    assert recorded["bucket"] == "b"
    # params from config + CLI override
    assert recorded["hyperparameters"]["foo"] == "bar"


def test_cli_init(tmp_path, monkeypatch):
    outfile = tmp_path / "jobber.yml"
    argv = ["init", "--path", str(outfile), "--region", "us-west-2", "--role-arn", "arn:aws:iam::123:role/Role"]
    cli.main(argv)
    assert outfile.exists()
    content = outfile.read_text()
    assert "build:" in content
    assert "push:" in content
    assert "submit:" in content
