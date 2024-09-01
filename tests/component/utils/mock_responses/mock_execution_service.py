import responses
from typing import List

from tests.common import DUMMY_BASE_URL


def mock_get_executions(executions: List[dict] = [], limit: int = 100, jit_event_id: str = None):
    url = f"{DUMMY_BASE_URL}/execution?limit={limit}"
    if jit_event_id:
        url += f"&jit_event_id={jit_event_id}"

    response = {
        'data': executions,
        'metadata': {
            'last_key': None,
            'count': len(executions),
        }
    }
    responses.add(
        responses.GET,
        url,
        json=response,
        status=200,
    )
