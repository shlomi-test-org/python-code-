from http import HTTPStatus

import pytest
from jit_utils.models.finding import AppRawControlFinding, \
    SchemaType, CloudRawControlFinding, RawControlFinding, \
    CodeRawControlFinding, FindingsPayload

from src.handlers.schema import get_schema, SchemaRequest
from tests.component.utils.get_handler_event import get_handler_event


@pytest.mark.parametrize("schema_type, expected_model", [
    [SchemaType.APPLICATION, AppRawControlFinding],
    [SchemaType.BASE, RawControlFinding],
    [SchemaType.CODE, CodeRawControlFinding],
    [SchemaType.CLOUD, CloudRawControlFinding],
])
def test_schema(schema_type: SchemaType, expected_model: FindingsPayload):
    event = get_handler_event(
        path_parameters=SchemaRequest(schema_type=schema_type).dict(),
        permissions=[]
    )
    response = get_schema(event, {})
    assert response["statusCode"] == HTTPStatus.OK
    assert response["body"] == expected_model.schema_json()


def test_get_schema_bad_request():
    response = get_schema({"pathParameters": {"schema_type": "bad_type", "version": "1"}, "requestContext": {
        "authorizer": {
            "permissions": []
        }}}, {})
    assert response["statusCode"] == HTTPStatus.BAD_REQUEST
