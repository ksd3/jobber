import types
import pytest
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

    class FakeECRInfo:
        def __init__(self, account_id, region, repo_name, image_tag):
            self.registry = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
            self.image_uri = f"{self.registry}/{repo_name}:{image_tag}"

    monkeypatch.setitem(
        sys.modules,
        "jobber.ecr_utils",
        types.SimpleNamespace(ECRInfo=FakeECRInfo, ensure_repo=fake_ensure_repo, ecr_login=fake_ecr_login),
    )
    monkeypatch.setattr(cli, "tag_image", fake_tag_image)
    monkeypatch.setattr(cli, "push_image", fake_push_image)
    monkeypatch.setattr(cli, "DockerImage", cli.DockerImage)

    # Patch boto3.Session used inside cmd_push
    import jobber.cli as cli_module

    def fake_session(region_name=None):
        return FakeSession(region_name)

    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(Session=fake_session))

    args = SimpleNamespace(image="local/img", repo="repo", tag="t", region="us-east-1", provider=None, project=None, artifact_repo=None)
    cli.cmd_push(args)
    assert calls["ensure_repo"] == "repo"
    assert calls["pushed"].endswith(":t")


def test_cmd_submit(monkeypatch):
    recorded = {}

    def fake_submit_job(**kwargs):
        recorded.update(kwargs)
        return "job-123"

    monkeypatch.setitem(sys.modules, "jobber.sm_submit", types.SimpleNamespace(submit_job=fake_submit_job))

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
        provider=None,
        params=None,
        gcs_bucket=None,
        gcs_prefix=None,
        machine_type=None,
        accelerator_type=None,
        accelerator_count=None,
        replica_count=None,
        service_account=None,
        network=None,
        subnet=None,
        ensure_data=True,
        use_spot=False,
        max_wait_seconds=None,
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

    monkeypatch.setitem(sys.modules, "jobber.sm_submit", types.SimpleNamespace(submit_job=fake_submit_job))

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
    argv = ["init", "--path", str(outfile), "--region", "us-west-2", "--role-arn", "arn:aws:iam::123:role/Role", "--provider", "aws"]
    monkeypatch.setattr("builtins.input", lambda prompt='': "")
    cli.main(argv)
    assert outfile.exists()
    content = outfile.read_text()
    assert "provider: aws" in content
    assert "build:" in content
    assert "push:" in content
    assert "submit:" in content


def test_cmd_push_gcp(monkeypatch):
    calls = {}

    def fake_auth(region):
        calls["auth"] = region

    def fake_push_image(src_img, target_ref):
        calls["tag"] = (src_img.ref, target_ref.uri)
        calls["pushed"] = target_ref.uri

    def fake_ensure(project, region, repo):
        calls["ensure"] = (project, region, repo)

    monkeypatch.setattr(cli, "gcp_auth", fake_auth)
    monkeypatch.setattr(cli, "gcp_push", fake_push_image)
    monkeypatch.setattr(cli, "gcp_ensure_repo", fake_ensure)

    args = SimpleNamespace(
        image="local/img",
        repo=None,
        tag="t",
        region="us-central1",
        provider="gcp",
        project="proj",
        artifact_repo="repo",
    )
    cli.cmd_push(args)
    assert calls["auth"] == "us-central1"
    assert calls["pushed"].startswith("us-central1-docker.pkg.dev/proj/repo/")
    assert calls["ensure"] == ("proj", "us-central1", "repo")


def test_cmd_push_gcp_from_config(tmp_path, monkeypatch):
    calls = {}

    conf = tmp_path / "jobber.yml"
    conf.write_text(
        "provider: gcp\n"
        "push:\n"
        "  project: proj\n"
        "  region: us-central1\n"
        "  artifact-repo: repo\n"
    )

    def fake_auth(region):
        calls["auth"] = region

    def fake_push_image(src_img, target_ref):
        calls["pushed"] = target_ref.uri

    def fake_ensure(project, region, repo):
        calls["ensure"] = (project, region, repo)

    monkeypatch.setattr(cli, "gcp_auth", fake_auth)
    monkeypatch.setattr(cli, "gcp_push", fake_push_image)
    monkeypatch.setattr(cli, "gcp_ensure_repo", fake_ensure)

    argv = ["push", "--config", str(conf), "--image", "local/img"]
    cli.main(argv)
    assert calls["auth"] == "us-central1"
    assert calls["pushed"].startswith("us-central1-docker.pkg.dev/proj/repo/")
    assert calls["ensure"] == ("proj", "us-central1", "repo")


def test_cmd_sync_gcp(monkeypatch, tmp_path):
    calls = {}

    def fake_ensure(bucket, region=None):
        calls["bucket"] = (bucket, region)

    def fake_sync(src, dest):
        calls["sync"] = (str(src), dest)

    monkeypatch.setattr(cli, "gcp_storage", types.SimpleNamespace(ensure_bucket=fake_ensure, sync_local_to_gcs=fake_sync))

    src = tmp_path / "data"
    src.mkdir()
    args = SimpleNamespace(src=str(src), dest="gs://bucket/prefix", region="us-central1", provider="gcp")
    cli.cmd_sync(args)
    assert calls["bucket"] == ("bucket", "us-central1")
    assert calls["sync"][1] == "gs://bucket/prefix"


def test_cmd_sync_gcp_inferred(monkeypatch, tmp_path):
    calls = {}

    def fake_ensure(bucket, region=None):
        calls["bucket"] = bucket

    def fake_sync(src, dest):
        calls["dest"] = dest

    monkeypatch.setattr(cli, "gcp_storage", types.SimpleNamespace(ensure_bucket=fake_ensure, sync_local_to_gcs=fake_sync))

    src = tmp_path / "data2"
    src.mkdir()
    args = SimpleNamespace(src=str(src), dest="gs://b/p", region=None, provider=None)
    cli.cmd_sync(args)
    assert calls["bucket"] == "b"
    assert calls["dest"] == "gs://b/p"


def test_cmd_submit_gcp(monkeypatch):
    recorded = {}

    def fake_submit(**kwargs):
        recorded.update(kwargs)
        return "projects/p/locations/r/customJobs/123"

    fake_module = types.SimpleNamespace(submit_job=fake_submit, gcp_storage=None)
    # Override module cache and jobber attribute so the import inside cmd_submit uses the fake.
    monkeypatch.setitem(sys.modules, "jobber.vertex_submit", fake_module)
    import jobber as jobber_pkg

    monkeypatch.setattr(jobber_pkg, "vertex_submit", fake_module, raising=False)

    args = SimpleNamespace(
        image_uri="us-central1-docker.pkg.dev/p/r/img:tag",
        role_arn=None,
        bucket=None,
        prefix=None,
        region="us-central1",
        entry_point="train.py",
        source_dir=".",
        instance_type=None,
        instance_count=None,
        job_name="job",
        param=["epochs=1"],
        tail_logs=True,
        provider="gcp",
        params=None,
        gcs_bucket="b",
        gcs_prefix="p",
        machine_type="n1-standard-4",
        accelerator_type=None,
        accelerator_count=None,
        replica_count=1,
        service_account=None,
        network=None,
        subnet=None,
        ensure_data=True,
        use_spot=False,
        max_wait_seconds=None,
        project="proj",
    )
    cli.cmd_submit(args)
    assert recorded["project"] == "proj"
    assert recorded["region"] == "us-central1"
    assert recorded["bucket"] == "b"
    assert recorded["prefix"] == "p"
    assert recorded["args"]["epochs"] == "1"


def test_cli_init_gcp(tmp_path, monkeypatch):
    outfile = tmp_path / "jobber.yml"
    argv = ["init", "--path", str(outfile), "--region", "us-central1", "--provider", "gcp"]
    monkeypatch.setattr("builtins.input", lambda prompt='': "")
    cli.main(argv)
    assert outfile.exists()
    content = outfile.read_text()
    assert "provider: gcp" in content
    assert "project:" in content
    assert "gcs-bucket" in content


def test_cmd_submit_gcp_missing_deps(monkeypatch, capsys):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        fromlist = k.get("fromlist", a[2] if len(a) > 2 else ()) or ()
        if name.startswith("jobber.vertex_submit") or (name == "jobber" and "vertex_submit" in fromlist):
            raise ModuleNotFoundError("jobber.vertex_submit")
        return real_import(name, *a, **k)

    # Ensure clean slate so the import will be attempted
    sys.modules.pop("jobber.vertex_submit", None)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    import jobber as jobber_pkg
    if hasattr(jobber_pkg, "vertex_submit"):
        delattr(jobber_pkg, "vertex_submit")
    for mod in list(sys.modules):
        if mod.startswith("google") or mod.startswith("jobber.vertex_submit"):
            sys.modules.pop(mod, None)

    # Prevent gsutil calls during this test by stubbing gcp_storage
    monkeypatch.setattr(
        sys.modules.setdefault("jobber.gcp_storage", types.SimpleNamespace()),
        "upload_placeholder",
        lambda b, p: None,
    )

    args = SimpleNamespace(
        image_uri="uri",
        role_arn=None,
        bucket=None,
        prefix="p",
        region="us-central1",
        entry_point="train.py",
        source_dir=".",
        instance_type=None,
        instance_count=None,
        job_name="job",
        param=[],
        tail_logs=False,
        provider="gcp",
        params=None,
        gcs_bucket="b",
        gcs_prefix="p",
        machine_type="n1-standard-4",
        accelerator_type=None,
        accelerator_count=None,
        replica_count=1,
        service_account=None,
        network=None,
        subnet=None,
        ensure_data=True,
        use_spot=False,
        max_wait_seconds=None,
        project="proj",
    )
    with pytest.raises(SystemExit):
        cli.cmd_submit(args)
    err = capsys.readouterr().err
    assert "google-cloud-aiplatform" in err
