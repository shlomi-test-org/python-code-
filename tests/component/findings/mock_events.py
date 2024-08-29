# noqa: E501
from jit_utils.utils.permissions import Read

from tests.component.utils.get_handler_event import get_handler_event

token = "my-token"
tenant_id = "19881e72-6d3b-49df-b79f-298ad89b8056"

GET_FINDINGS_EVENT_NO_FILTERS = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "sort": "created_at",
        "page_limit": "3",
        "sort_desc": "true",
        "next_page_key": None,
    },
    permissions=[Read.FINDINGS],
)
GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "filters": '{"created_at_start":"2023-01-28",'
                   '"created_at_end":"2023-08-28",'
                   '"ignored":[false],'
                   '"resolution":["OPEN"],'
                   '"issue_severity":["HIGH"]}',
        "sort": "created_at",
        "page_limit": "3",
        "sort_desc": "true",
        "next_page_key": None,
    },
    permissions=[Read.FINDINGS],
)

GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT_AS_CSV = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters=GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT["queryStringParameters"],
    headers={
        "Accept": "text/csv+link"
    },
    permissions=[Read.FINDINGS],
)

GET_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "filters": '{"ignored":[true],"issue_severity":["HIGH"]}',
        "sort": "created_at",
        "page_limit": "3",
        "sort_desc": "true",
        "next_page_key": None,
    },
    permissions=[Read.FINDINGS],
)

COUNT_OPEN_NOT_IGNORED_HIGH_SEVERITY_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "filters": '{"resolution":["OPEN"],"issue_severity":["HIGH"], "ignored":[false]}'
    },
    permissions=[Read.FINDINGS],
)

COUNT_FINDINGS_NO_FILTERS_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    permissions=[Read.FINDINGS],
)

COUNT_FINDINGS_ALL_RESOLUTION_FILTERS_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "filters": '{"resolution":["OPEN", "FIXED"]}'
    },
    permissions=[Read.FINDINGS],
)
COUNT_FIXED_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "filters": '{"resolution":"FIXED","issue_severity":"HIGH", "ignored":[false]}'
    },
    permissions=[Read.FINDINGS],
)
COUNT_PLAN_ITEM_INDEX_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "filters": '{"resolution":"OPEN","backlog":true,"ignored":false,"plan_item":["plan_item1"]}'
    },
    permissions=[Read.FINDINGS],
)
COUNT_PLAN_ITEM_INDEX_GROUP_BY_PLAN_ITEM_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "group_by": "plan_item",
        "filters": '{"resolution":"OPEN","backlog":true,"ignored":false}'
    },
    permissions=[Read.FINDINGS],
)

COUNT_NO_FILTERS_FINDINGS_GROUP_BY_CONTROL_NAME_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "group_by": "control_name",
    },
    permissions=[Read.FINDINGS],
)

COUNT_OPEN_NOT_IGNORED_FINDINGS_GROUP_BY_CONTROL_NAME_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "group_by": "control_name",
        "filters": '{"resolution":["OPEN"], "ignored":[false]}'
    },
    permissions=[Read.FINDINGS],
)


GET_TEAM_FINDINGS_EVENT = get_handler_event(
    token=token,
    tenant_id=tenant_id,
    query_string_parameters={
        "filters": '{"team":["team1"],"issue_severity":["HIGH"]}',
        "sort": "created_at",
        "page_limit": "3",
        "sort_desc": "true",
        "next_page_key": None,
    },
    permissions=[Read.FINDINGS],
)
