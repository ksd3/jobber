import types
from jobber import sm_submit


def test_submit_job_signature():
    # Just ensure the function exists and can be called with dummy params; no AWS call is made.
    assert hasattr(sm_submit, "submit_job")
    assert isinstance(sm_submit.submit_job, types.FunctionType)


def test_placeholder_upload(monkeypatch):
    calls = {}

    class FakeS3:
        def list_objects_v2(self, Bucket, Prefix, MaxKeys):
            calls["listed"] = (Bucket, Prefix)
            return {"KeyCount": 0}

        def put_object(self, Bucket, Key, Body):
            calls["put"] = (Bucket, Key, Body)

    class FakeSession:
        def client(self, name):
            assert name == "s3"
            return FakeS3()

    monkeypatch.setattr(sm_submit.boto3, "Session", lambda region_name=None: FakeSession())

    class DummyEstimator:
        latest_training_job = type("J", (), {"name": "job"})()

        def __init__(self, *a, **k):
            pass

        def fit(self, *a, **k):
            pass

    monkeypatch.setattr(sm_submit, "Estimator", DummyEstimator)
    job = sm_submit.submit_job(
        image_uri="uri",
        role_arn="arn",
        bucket="b",
        prefix="p",
        region=None,
        entry_point=None,
        source_dir=".",
        hyperparameters={},
        instance_type="ml.m5.xlarge",
        ensure_data=True,
    )
    assert calls["put"][1].endswith("placeholder.txt")
