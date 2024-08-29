from aws_requests_auth.boto_utils import BotoAWSRequestsAuth
import os
from typing import Optional
from urllib.parse import urlparse

from src.lib.constants import DEPLOYMENT_STAGE, LOCAL, TEST, REGION_NAME


def sign(url: str) -> BotoAWSRequestsAuth:
    stage = os.environ[DEPLOYMENT_STAGE]
    host: Optional[str]
    if stage in [LOCAL, TEST]:
        host = url.split("http://")[1].split("restapis")[0]
    else:
        host = urlparse(url).hostname

    if not host:
        raise ValueError("Could not parse the host from the url")

    return BotoAWSRequestsAuth(aws_host=host, aws_region=os.environ[REGION_NAME], aws_service="execute-api")
