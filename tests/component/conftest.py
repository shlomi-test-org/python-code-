import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def prepare_env_vars():
    os.environ['DEPLOYMENT_STAGE'] = 'dev'
    os.environ['API_HOST'] = 'api.dummy.jit.io'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    os.environ['AWS_ACCOUNT_ID'] = '123456789'
    os.environ['AWS_REGION_NAME'] = 'us-east-1'
