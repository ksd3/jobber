import types
from jobber import sm_submit


def test_submit_job_signature():
    # Just ensure the function exists and can be called with dummy params; no AWS call is made.
    assert hasattr(sm_submit, "submit_job")
    assert isinstance(sm_submit.submit_job, types.FunctionType)


def test_placeholder_upload(monkeypatch):
    calls = {}

    class FakeS3:
        def __init__(self):
            self.meta = types.SimpleNamespace(region_name=None)

        def head_bucket(self, Bucket):
            calls["head"] = Bucket
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "NoSuchBucket"}}, "HeadBucket")

        def create_bucket(self, Bucket, CreateBucketConfiguration=None):
            calls["created"] = (Bucket, CreateBucketConfiguration)

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

    class DummyTrainer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            calls["trainer_kwargs"] = kwargs
            self._latest_training_job = types.SimpleNamespace(training_job_name="job")

        def train(self, *a, **k):
            pass

    monkeypatch.setattr(sm_submit, "ModelTrainer", DummyTrainer)
    monkeypatch.setattr(sm_submit, "Session", lambda boto_session=None: types.SimpleNamespace(boto_session=boto_session))
    monkeypatch.setattr(sm_submit, "_stream_training_logs", lambda job_name, session, poll=5: calls.setdefault("stream", job_name))
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
        tail_logs=True,
        ensure_data=True,
        use_spot=True,
        max_wait_seconds=123,
    )
    assert calls["put"][1].endswith("placeholder.txt")
    assert calls["created"][0] == "b"
    assert calls["stream"] == "job"
    assert isinstance(calls["trainer_kwargs"]["compute"], object)
    assert calls["trainer_kwargs"]["compute"].enable_managed_spot_training is True
    assert calls["trainer_kwargs"]["stopping_condition"].max_wait_time_in_seconds == 123
    assert calls["trainer_kwargs"]["stopping_condition"].max_runtime_in_seconds == 123
    assert job == "job"
