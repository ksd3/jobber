from jobber.ecr_utils import ECRInfo


def test_ecr_info():
    info = ECRInfo(account_id="123456789012", region="us-east-1", repo_name="repo", image_tag="t")
    assert info.registry == "123456789012.dkr.ecr.us-east-1.amazonaws.com"
    assert info.image_uri == "123456789012.dkr.ecr.us-east-1.amazonaws.com/repo:t"
