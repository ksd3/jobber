import sys
import types

# Stub google.cloud.aiplatform_v1 before importing module under test
fake_aiplatform = types.ModuleType("google.cloud.aiplatform_v1")
fake_aiplatform.JobServiceClient = type("JobServiceClient", (), {})  # placeholder for annotations
fake_aiplatform.JobState = lambda s: types.SimpleNamespace(name=s if isinstance(s, str) else "UNKNOWN")
sys.modules["google"] = types.ModuleType("google")
sys.modules["google.cloud"] = types.ModuleType("google.cloud")
sys.modules["google.cloud.aiplatform_v1"] = fake_aiplatform

from jobber import vertex_submit


def test_builds_custom_job(monkeypatch):
    calls = {}

    class FakeResponse:
        def __init__(self, name):
            self.name = name

    class FakeClient:
        def __init__(self, *a, **k):
            calls["client_opts"] = k.get("client_options")

        def common_location_path(self, project, region):
            return f"projects/{project}/locations/{region}"

        def create_custom_job(self, parent, custom_job):
            calls["parent"] = parent
            calls["job"] = custom_job
            return FakeResponse("projects/p/locations/r/customJobs/123")

        def get_custom_job(self, name):
            return types.SimpleNamespace(state="JOB_STATE_SUCCEEDED")  # matches JobState lambda

    monkeypatch.setattr(vertex_submit, "aiplatform_v1", types.SimpleNamespace(JobServiceClient=FakeClient, JobState=lambda s: types.SimpleNamespace(name=s)))
    monkeypatch.setattr(vertex_submit, "gcp_storage", types.SimpleNamespace(upload_placeholder=lambda b, p: calls.setdefault("placeholder", (b, p))))
    calls["gcloud"] = []

    class FakeProc:
        def __init__(self, cmd):
            calls["gcloud"].append(cmd)
            self._code = None

        def poll(self):
            return self._code

        def terminate(self):
            self._code = 0

        def wait(self, timeout=None):
            self._code = 0
            return 0

        def kill(self):
            self._code = -9

    monkeypatch.setattr(vertex_submit.subprocess, "Popen", lambda cmd: FakeProc(cmd))

    job_name = vertex_submit.submit_job(
        project="proj",
        region="us-central1",
        image_uri="us-central1-docker.pkg.dev/proj/repo/img:tag",
        bucket="b",
        prefix="p",
        entry_point="train.py",
        source_dir=None,
        args={"epochs": 1},
        machine_type="n1-standard-4",
        accelerator_type="NVIDIA_TESLA_T4",
        accelerator_count=1,
        replica_count=2,
        job_name="jobber-test",
        service_account="sa@proj.iam.gserviceaccount.com",
        network="n",
        subnet="sn",
        ensure_data=True,
        tail_logs=True,
    )
    assert calls["client_opts"]["api_endpoint"] == "us-central1-aiplatform.googleapis.com"
    assert "job" in calls
    spec = calls["job"]["job_spec"]["worker_pool_specs"][0]
    assert spec["replica_count"] == 2
    assert spec["machine_spec"]["accelerator_type"] == "NVIDIA_TESLA_T4"
    assert spec["machine_spec"]["accelerator_count"] == 1
    assert calls["job"]["display_name"] == "jobber-test"
    assert calls["placeholder"] == ("b", "p")
    assert job_name.endswith("customJobs/123")
    assert calls["gcloud"][0][:4] == ["gcloud", "ai", "custom-jobs", "stream-logs"]
