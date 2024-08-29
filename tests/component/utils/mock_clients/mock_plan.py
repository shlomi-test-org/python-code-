from typing import List

import responses


def mock_get_job_scopes(workflow_slug: str, job_name: str, response_scopes: List = []):
    url = 'https://api.dummy.jit.io/plan/template/scopes' \
          f'?workflow_slug={workflow_slug}&job_name={job_name}'

    res_data = [{
        "workflow_slug": workflow_slug,
        "job_name": job_name,
        "scopes": scope['scopes'],
        "plan_item_slug": scope['plan_item_slug']
    } for scope in response_scopes]

    responses.add(responses.GET, url, status=200, json=res_data)
