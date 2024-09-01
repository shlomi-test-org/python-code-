import json

import responses
from jit_utils.utils.permissions import Read

from src.handlers.ignore_rules.get_ignore_rules import handler
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_mongo_data_api import MongoDataApiMock
from tests.fixtures import build_ignore_rule_dict


@responses.activate
def test_get_ignore_rules(mocker, env_variables):
    """
    Test the 'get ignore rules' handler
    for a given tenant_id, asset_id and control_name.

    Setup:
    1. Insert 20 ignore rules to the database with the new ignore rule version,
     (no direct asset_id, control_name and fingerprint).
    2. Mock requests and update many Mongo data api call.

    Test:
    Call the handler

    Assert:
    1. The response status code should be 200.
    2. The ignore rules matching the query params should return with content_type field
    """
    # Assign
    now_string = "2022-01-14T00:00:00"

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    tenant_id = "tenant_id"
    asset_id = "asset_id"
    control_name = "kics"

    ignore_rules = []
    for i in range(20):
        fingerprint = f"fingerprint_{i}"
        ignore_rule = build_ignore_rule_dict(ignore_rule_id=f"ignore_rule_id_{i}",
                                             tenant_id=tenant_id,
                                             created_at=now_string,
                                             control_name=control_name,
                                             asset_id=asset_id,
                                             fingerprint=fingerprint,
                                             )
        ignore_rules.append(ignore_rule)

    event = get_handler_event(
        tenant_id=tenant_id,
        token='token',
        path_parameters={"asset_id": asset_id, "control_name": control_name},
        permissions=[Read.IGNORE_RULES]
    )

    mocked_data_api.db.ignore_rules.insert_many(ignore_rules)

    # Act
    response = handler(event, {})
    # Assert
    assert response['statusCode'] == 200
    assert len(json.loads(response['body'])['ignore_rules']) == 20
    # ensure the ignore-rules returned have rule content field - used in the entrypoint
    for ignore_rule in json.loads(response['body'])['ignore_rules']:
        assert ignore_rule['rule_content'] is not None
        assert ignore_rule['type'] == 'fingerprint'


@responses.activate
def test_get_ignore_rules_in_scale(mocker, env_variables):
    """
    Test the 'get ignore rules' handler
    for a given tenant_id, asset_id and control_name.

    Setup:
    1. Insert 301 ignore rules to the database
    2. Mock requests and update many Mongo data api call.

    Test:
    Call the handler

    Assert:
    1. The response status code should be 200.
    2. The ignore rules matching the query params should return with content_type field
    3. 300 ignore rules should be returned
    """
    # Assign
    now_string = "2022-01-14T00:00:00"

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    tenant_id = "tenant_id"
    asset_id = "asset_id"
    control_name = "kics"
    control_name_2 = "zap"

    ignore_rules = [build_ignore_rule_dict(ignore_rule_id=f"ignore_rule_id_{i}",
                                           tenant_id=tenant_id,
                                           created_at=now_string,
                                           control_name=control_name,
                                           asset_id=asset_id,
                                           fingerprint=f"fingerprint_{i}")
                    for i in range(300)]
    ignore_rules.append(build_ignore_rule_dict(ignore_rule_id=f"ignore_rule_id_{301}",
                                               tenant_id=tenant_id,
                                               created_at=now_string,
                                               control_name=control_name_2,
                                               asset_id=asset_id,
                                               fingerprint=f"fingerprint_{301}"))

    event = get_handler_event(tenant_id=tenant_id,
                              token='token',
                              path_parameters={"asset_id": asset_id, "control_name": control_name},
                              permissions=[Read.IGNORE_RULES])

    mocked_data_api.db.ignore_rules.insert_many(ignore_rules)

    # Act
    response = handler(event, {})
    # Assert
    assert response['statusCode'] == 200
    assert len(json.loads(response['body'])['ignore_rules']) == 300
