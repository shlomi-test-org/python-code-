import json
import random
from datetime import datetime, timedelta
from http import HTTPStatus

import responses
from freezegun import freeze_time
from jit_utils.models.findings.constants import MAX_TICKETS_FOR_FINDING, MAX_FINDING_IDS
from jit_utils.models.findings.entities import Ticket
from jit_utils.models.integration.entities import TicketResponse
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.handlers.findings.create_ticket import handler
from src.lib.constants import FINDINGS_BUS_NAME
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_mongo_driver import mock_mongo_driver

from tests.fixtures import build_finding_dict
from tests.mock.factories import TicketFactory
from jit_utils.models.findings.entities import Finding

TENANT_ID = "9df0c0ae-b497-40ba-bc78-d486aaa083d0"
FRONTEGG_USER_ID = "9df0c0ae-b497-40ba-bc78-d486aaa083d0"
VENDOR = "jira"
MOCK_CREATE_TICKET_INTEGRATION_URL = f"https://api.dummy.jit.io/integration/internal/{TENANT_ID}/ticket"


def create_api_event(finding_ids):
    body = {
        "vendor": VENDOR,
        "type": "findings",
        "title": "S3 Buckets should enforce encryption of data transfers using Secure Sockets Layer (SSL)",
        "finding_ids": finding_ids,
    }
    return get_handler_event(
        body=body,
        tenant_id=TENANT_ID,
        user_id=FRONTEGG_USER_ID,
        permissions=["jit.ticketing.write", "jit.findings.write"]
    )


def setup_mock_mongo(mocker, findings):
    mongo_client = mock_mongo_driver(mocker)
    findings_collection = mongo_client.findings
    findings_collection.insert_many(findings)
    return findings_collection


def setup_mock_ticket_response():
    mock_ticket = TicketResponse(
        id='ticket_id',
        name='ticket_name',
        link='http://example.com/ticket',
    )
    responses.add(
        responses.POST,
        MOCK_CREATE_TICKET_INTEGRATION_URL,
        json=mock_ticket.dict(),
        status=HTTPStatus.OK
    )
    return mock_ticket


@freeze_time("2023-01-01")
@responses.activate
def test_handle_ticket_creation__happy_flow(mocker, monkeypatch):
    """
    Setup:
        1) Mock MongoDB driver.
        2) Insert findings to the mocked collection.
        3) Mock create ticket integration request.

    Test:
        1) Call the handler once.

    Verify:
        1) The findings were updated with the new ticket.
    """
    finding_ids = ["5c5d3bf8-59da-4a7d-a20c-eda720676f30", "5c5d3bf8-59da-4a7d-a20c-eda720676f29"]
    api_event = create_api_event(finding_ids)
    now = datetime.utcnow().isoformat()
    findings = [build_finding_dict(finding_id=finding_id, tenant_id=TENANT_ID, backlog=True,
                                   location=random.choice([None, "location2"])
                                   ) for finding_id in finding_ids]
    findings_collection = setup_mock_mongo(mocker, findings)
    mock_ticket = setup_mock_ticket_response()

    with mock_eventbridge(
            FINDINGS_BUS_NAME) as get_sent_events:
        response = handler(api_event, {})

        findings_after_update = list(findings_collection.find())
        expected_ticket = Ticket(
            ticket_id=mock_ticket.id,
            ticket_url=mock_ticket.link,
            ticket_name=mock_ticket.name,
            user_id=FRONTEGG_USER_ID,
            vendor=VENDOR,
            created_at=now
        )

        # Assert
        assert response["statusCode"] == HTTPStatus.CREATED
        body = json.loads(response['body'])
        assert body == TicketResponse(
            id=expected_ticket.ticket_id,
            name=expected_ticket.ticket_name,
            link=expected_ticket.ticket_url
        )

        for finding in findings_after_update:
            assert len(finding["tickets"]) == 1
            assert finding["tickets"][0] == expected_ticket
            assert finding["modified_at"] == now

        # Assert ticket created event was sent
        events = get_sent_events()
        assert len(events) == 2
        assert events[0]['detail'] == {'tenant_id': TENANT_ID,
                                       'finding_ids': finding_ids,
                                       **expected_ticket.dict()}
        assert events[0]['detail-type'] == 'findings-ticket-created'
        assert events[1]['detail-type'] == 'findings-updated'
        findings[0]['tickets'] = [expected_ticket.dict()]
        findings[1]['tickets'] = [expected_ticket.dict()]
        findings = [Finding(**finding) for finding in findings]
        assert events[1]['detail']['findings'] == findings


@freeze_time("2023-01-01")
@responses.activate
def test_handle_ticket_creation_with_existing_tickets(mocker):
    """
    Setup:
        1) Mock MongoDB driver.
        2) Insert finding with existing tickets to the mocked collection.
        3) Mock create ticket integration request.

    Test:
        1) Call the handler once.

    Verify:
        1) The new ticket is appended to the existing tickets.
    """
    finding_ids = ["5c5d3bf8-59da-4a7d-a20c-eda720676f29"]
    api_event = create_api_event(finding_ids)
    now = datetime.utcnow().isoformat()
    yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
    existing_ticket = Ticket(
        ticket_id="ticket123",
        ticket_url="http://example.com/ticket123",
        ticket_name="Sample Ticket",
        user_id="user123",
        vendor="vendorX",
        created_at=yesterday
    )
    finding = build_finding_dict(finding_id=finding_ids[0],
                                 tenant_id=TENANT_ID,
                                 tickets=[existing_ticket]
                                 )
    findings_collection = setup_mock_mongo(mocker, [finding])
    mock_ticket = setup_mock_ticket_response()

    # Act
    with mock_eventbridge(
            FINDINGS_BUS_NAME) as get_sent_events:
        response = handler(api_event, {})

        finding_after_update = findings_collection.find_one()
        new_ticket = Ticket(
            ticket_id=mock_ticket.id,
            ticket_url=mock_ticket.link,
            ticket_name=mock_ticket.name,
            user_id=FRONTEGG_USER_ID,
            vendor=VENDOR,
            created_at=now
        )

        # Assert
        assert response["statusCode"] == HTTPStatus.CREATED
        body = json.loads(response['body'])
        assert body == TicketResponse(
            id=new_ticket.ticket_id,
            name=new_ticket.ticket_name,
            link=new_ticket.ticket_url
        )

        assert len(finding_after_update["tickets"]) == 2
        assert finding_after_update["tickets"][0] == existing_ticket
        assert finding_after_update["tickets"][1] == new_ticket
        assert finding_after_update["modified_at"] == now

        # Assert ticket created event was sent
        events = get_sent_events()
        assert len(events) == 1
        assert events[0]['detail'] == {'tenant_id': TENANT_ID,
                                       'finding_ids': finding_ids,
                                       **new_ticket.dict()}


@freeze_time("2023-01-01")
@responses.activate
def test_handle_ticket_creation__finding_ids_not_found(mocker):
    """
    Setup:
        1) Mock MongoDB driver.
        2) Insert findings with different tenant_id to the mocked collection.

    Test:
        1) Call the handler once.

    Verify:
        1) An error response is returned for not existing findings.
    """
    finding_ids = ["5c5d3bf8-59da-4a7d-a20c-eda720676f30"]
    api_event = create_api_event(finding_ids)
    findings = [build_finding_dict(finding_id=f"finding-{i}", tenant_id=TENANT_ID) for i in range(3)]
    setup_mock_mongo(mocker, findings)

    response = handler(api_event, {})

    assert response["statusCode"] == HTTPStatus.BAD_REQUEST
    body = json.loads(response['body'])
    assert body["message"] == f"Could not find findings with ids: {finding_ids}"
    assert body["error"] == "INVALID_INPUT"


@responses.activate
def test_create_ticket_exceeding_ticket_limit__bad_request(mocker):
    """
    Setup:
        1) Mock MongoDB driver.
        2) Insert finding with exceeding tickets to the mocked collection.
    Test:
        - Call the handler with the API event.

    Verify:
        - The response status code is HTTPStatus.BAD_REQUEST.
        - The exception ExceededNumberOfTicketsForFinding is raised.
        - The error response matches the expected error response format.
    """
    finding_ids = ["5c5d3bf8-59da-4a7d-a20c-eda720676f29", "5c5d3bf8-59da-4a7d-a20c-eda720676f30"]
    api_event = create_api_event(finding_ids)
    exceeding_ticket_mock_finding = build_finding_dict(finding_id=finding_ids[0],
                                                       tenant_id=TENANT_ID,
                                                       tickets=[TicketFactory.build() for _ in
                                                                range(MAX_TICKETS_FOR_FINDING + 1)])
    findings = [exceeding_ticket_mock_finding, build_finding_dict(finding_id=finding_ids[1], tenant_id=TENANT_ID)]
    setup_mock_mongo(mocker, findings)

    response = handler(api_event, {})
    assert response["statusCode"] == HTTPStatus.BAD_REQUEST
    body = json.loads(response['body'])
    assert body["message"] == ('Exceeded the maximum number of tickets for finding, which is 10,finding_id: '
                               f'{exceeding_ticket_mock_finding.get("id")}')


@responses.activate
def test_create_ticket_exceeding_finding_ids__bad_request():
    """
    Number of finding IDs exceeds the limit in the request

      Setup:
        1) Mock MongoDB driver.
    Test:
        - Call the handler with the API event.
    Act:
        - Call the handler with the API event
    Assert:
        - The response status code is HTTPStatus.BAD_REQUEST
        - The exception ExceededNumberOfFindingIds is raised
        - The error response matches the expected error response format
    """
    finding_ids = [f"finding-{i}" for i in range(MAX_FINDING_IDS + 1)]
    api_event = create_api_event(finding_ids)

    response = handler(api_event, {})

    assert response["statusCode"] == HTTPStatus.BAD_REQUEST
    body = json.loads(response['body'])
    assert body["message"] == f"Exceeded the maximum number of finding ids, which is {MAX_FINDING_IDS}"


@freeze_time("2023-01-01")
@responses.activate
def test_handle_ticket_creation__integration_service_error(mocker):
    """
    Setup:
        1) Mock MongoDB driver.
        2) Insert findings to the mocked collection.
        3) Mock failed create ticket integration request.

    Test:
        1) Call the handler once.

    Verify:
        1) The findings were not updated with the new ticket.
        2) An error response is returned.
    """
    finding_ids = ["5c5d3bf8-59da-4a7d-a20c-eda720676f29", "5c5d3bf8-59da-4a7d-a20c-eda720676f30"]
    api_event = create_api_event(finding_ids)
    findings = [build_finding_dict(finding_id=finding_id, tenant_id=TENANT_ID) for finding_id in finding_ids]
    findings_collection = setup_mock_mongo(mocker, findings)

    # Mock failed create ticket integration request
    responses.add(
        responses.POST,
        MOCK_CREATE_TICKET_INTEGRATION_URL,
        json={"error": "WORKFLOW_NOT_ENABLED",
              "message": "Some error message"},
        status=HTTPStatus.BAD_REQUEST
    )

    response = handler(api_event, {})

    # Verify the response
    assert response["statusCode"] == HTTPStatus.BAD_REQUEST
    body = json.loads(response["body"])
    assert body["message"] == "Some error message"

    # Verify the findings were not updated with the new ticket
    findings_after_update = list(findings_collection.find())
    for finding in findings_after_update:
        assert "tickets" not in finding or len(finding["tickets"]) == 0
