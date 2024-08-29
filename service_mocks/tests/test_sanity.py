from http import HTTPStatus

import requests

DOCKER_HOST = "localhost:8000"


def test_get_root():
    response = requests.get(f"http://{DOCKER_HOST}/health")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "UP"}
