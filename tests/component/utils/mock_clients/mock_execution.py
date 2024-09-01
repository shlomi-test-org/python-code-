import responses


def mock_get_execution_api(jit_event_id: str, execution_id: str, tenant_id: str):
    execution = {"tenant_id": tenant_id, "execution_id": execution_id,
                 "jit_event_name": "merge_default_branch",
                 "jit_event_id": jit_event_id, "plan_item_slug": "mock_plan_item"}
    responses.add(
        responses.GET,
        f'https://api.dummy.jit.io/execution/execution?jit_event_id={jit_event_id}&execution_id={execution_id}',
        json=execution,
        status=200,
    )
