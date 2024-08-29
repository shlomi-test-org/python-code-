from urllib.parse import urlencode

import responses
from typing import List

from jit_utils.jit_clients.team_service.endpoints import GET_TEAMS_URL
from jit_utils.models.teams.entities import FilterTeamBy

from tests.common import DUMMY_BASE_URL


def mock_get_teams_api(teams: List[dict], params: dict, status_code: int = 200):
    # Construct query string from params
    def get_value(raw_value):
        if isinstance(raw_value, FilterTeamBy):
            return raw_value.value
        return raw_value

    query_string = urlencode({key: get_value(value) for key, value in params.items() if value is not None})

    # Append the query string to the URL
    url = f"{GET_TEAMS_URL.format(base=f'{DUMMY_BASE_URL}/teams')}?{query_string}"

    responses.add(
        responses.GET,
        url,
        json={"metadata": {"limit": params["limit"], "count": len(teams)}, "data": teams},
        status=status_code,
    )
