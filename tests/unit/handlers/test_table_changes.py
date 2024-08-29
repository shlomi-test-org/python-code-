import json

import src.handlers.trigger_execution
from src.handlers.table_changes import execution_record_changed
from src.handlers.table_changes import resource_changed

EXECUTION_STREAM_EVENT = {
    'Records': [
        {'eventID': '66171e8103c421049cc6433e573586c6', 'eventName': 'MODIFY', 'eventVersion': '1.1',
         'eventSource': 'aws:dynamodb', 'awsRegion': 'us-east-1',
         'dynamodb': {'ApproximateCreationDateTime': 1670215223.0, 'Keys': {'SK': {
             'S': 'JIT_EVENT#5ef86229-de1e-410a-8a60-81052bebef27#RUN#d8d3c430-d990-4656-aad3-39abafa04453'},
             'PK': {
                 'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08'}},
                      'NewImage': {'tenant_id': {'S': '7ca2cba7-a783-48d2-ad5d-a15040560d08'},
                                   'plan_item_slug': {'S': 'item-iac-misconfiguration-detection'},
                                   'dispatched_at': {'S': '2022-12-05T04:39:36.479899'},
                                   'created_at': {'S': '2022-12-05T04:39:31.864654'},
                                   'GSI5SK': {'S': 'PRIORITY#1#CREATED_AT#2022-12-05t04:39:31.864654'},
                                   'asset_id': {'S': 'da24045c-d642-45ce-8870-fb862b1a3996'},
                                   'has_findings': {'BOOL': False}, 'plan_slug': {'S': 'jit-plan'},
                                   'execution_id': {'S': 'd8d3c430-d990-4656-aad3-39abafa04453'},
                                   'jit_event_id': {'S': '5ef86229-de1e-410a-8a60-81052bebef27'},
                                   'GSI4SK': {'S': '2022-12-05T04:39:31.864654'},
                                   'asset_name': {'S': 'test-1'},
                                   'GSI3SK': {'S': '2022-12-05T04:39:31.864654'},
                                   'GSI2SK': {'S': '2022-12-05T04:39:31.864654'},
                                   'vendor': {'S': 'github'},
                                   'GSI1SK': {'S': '2022-12-05T04:39:31.864654'},
                                   'job_runner': {'S': 'github_actions'}, 'SK': {
                              'S': 'JIT_EVENT#5ef86229-de1e-410a-8a60-81052bebef27#'
                                   'RUN#d8d3c430-d990-4656-aad3-39abafa04453'},
                                   'asset_type': {'S': 'repo'},
                                   'upload_findings_status': {'S': 'completed'},
                                   'registered_at_ts': {'N': '1670215201'}, 'additional_attributes': {
                              'M': {'owner': {'S': 'jitsecurity-cto'},
                                    'user_vendor_name': {'S': 'jit-shlomi'},
                                    'original_repository': {'S': 'test-1'},
                                    'user_vendor_id': {'S': '81581678'},
                                    'pull_request_title': {'S': 'Update README.md'}, 'languages': {
                                      'L': [{'S': 'JS'}, {'S': 'python'}, {'S': 'js_deps'},
                                            {'S': 'terraform'}, {'S': 'any'}]},
                                    'pull_request_number': {'S': '2'},
                                    'installation_id': {'S': '31832180'}, 'commits': {
                                      'M': {'base_sha': {'S': '21797ec887d3cf2ee8ffd9f8e23c3c80a05721ee'},
                                            'head_sha': {
                                                'S': 'b28f9ac874fac86c7146f6e459dde73b2752878a'}}},
                                    'app_id': {'S': '160590'}, 'branch': {'S': 'jit-shlomi-patch-2'}}},
                                   'control_type': {'S': 'detection'}, 'cloud_watch_context': {
                              'M': {'log_group_name': {
                                  'S': '/aws/lambda/execution-service-dev-log-orchestrator-events'},
                                  'log_stream_name': {
                                      'S': '2022/12/05/[$LATEST]f50019dc493944699e0936e36de60ceb'},
                                  'request_id': {'S': 'aaaec3d0-b9bc-404c-b7d8-a6f575885674'}}},
                                   'jit_event_name': {'S': 'pull_request_updated'},
                                   'run_id': {'S': '3616993728'}, 'dispatched_at_ts': {'N': '1670215176'},
                                   'registered_at': {'S': '2022-12-05T04:40:01.360751'}, 'GSI5PK': {
                              'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08#RUNNER#github_actions'
                                   '#STATUS#completed'},
                                   'resource_type': {'S': 'ci_high_priority'}, 'GSI4PK': {
                              'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08#PLAN_ITEM#item-'
                                   'iac-misconfiguration-detection#STATUS#completed'},
                                   'GSI3PK': {
                                       'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08#PLAN_ITEM'
                                            '#item-iac-misconfiguration-detection'},
                                   'GSI2PK': {
                                       'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08#STATUS#completed'},
                                   'control_image': {
                                       'S': 'ghcr.io/jitsecurity-controls/control-kics-alpine:latest'},
                                   'priority': {'N': '1'}, 'control_name': {'S': 'Run KICS'}, 'steps': {
                              'L': [{'M': {'name': {'S': 'Run KICS'}, 'uses': {
                                  'S': 'ghcr.io/jitsecurity-controls/control-kics-alpine:latest'},
                                           'params': {'M': {'args': {
                                               'S': 'scan -p /code -o /code/jit-report -f json --exclude'
                                                    '-severities INFO,MEDIUM,LOW --disable-secrets'},
                                               'output_file': {
                                                   'S': '/code/jit-report/results.json'}}}}}]},
                                   'completed_at': {'S': '2022-12-05T04:40:23.542119'},
                                   'created_at_ts': {'N': '1670215171'}, 'entity_type': {'S': 'job'},
                                   'GSI1PK': {'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08'},
                                   'job_name': {'S': 'iac-misconfig-detection'},
                                   'completed_at_ts': {'N': '1670215223'},
                                   'PK': {'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08'},
                                   'workflow_slug': {'S': 'workflow-iac-misconfiguration-detection'},
                                   'control_status': {'S': 'completed'}, 'status': {'S': 'completed'}},
                      'SequenceNumber': '1116577700000000022219065274', 'SizeBytes': 2641,
                      'StreamViewType': 'NEW_IMAGE'},
         'eventSourceARN': 'arn:aws:dynamodb:us-east-1:566740389182:table/Executions/stream/'
                           '2022-05-02T20:25:41.166'}]}

EXECUTION_STREAM_EVENT_EXPECTED = \
    {'metric_name': 'execution_update',
     'metadata': {'tenant_id': '7ca2cba7-a783-48d2-ad5d-a15040560d08', 'env_name': 'prod',
                  'event_id': '5ef86229-de1e-410a-8a60-81052bebef27',
                  'event_name': 'pull_request_updated', 'entity_type': 'job',
                  'plan_item_slug': 'item-iac-misconfiguration-detection',
                  'workflow_slug': 'workflow-iac-misconfiguration-detection',
                  'job_name': 'iac-misconfig-detection', 'control_name': 'Run KICS',
                  'control_image': 'ghcr.io/jitsecurity-controls/control-kics-alpine:latest',
                  'job_runner': 'github_actions',
                  'plan_slug': 'jit-plan', 'asset_type': 'repo', 'asset_name': 'test-1',
                  'asset_id': 'da24045c-d642-45ce-8870-fb862b1a3996', 'vendor': 'github',
                  'priority': 1, 'control_type': 'detection', 'execution_timeout': None},
     'data': {'execution_id': 'd8d3c430-d990-4656-aad3-39abafa04453',
              'created_at': '2022-12-05T04:39:31.864654', 'created_at_ts': 1670215171,
              'dispatched_at': '2022-12-05T04:39:36.479899',
              'dispatched_at_ts': 1670215176,
              'registered_at': '2022-12-05T04:40:01.360751',
              'registered_at_ts': 1670215201,
              'completed_at': '2022-12-05T04:40:23.542119', 'completed_at_ts': 1670215223,
              'run_id': '3616993728', 'status': 'completed', 'has_findings': False,
              'status_details': None, 'error_body': None,
              'upload_findings_status': 'completed', 'control_status': 'completed',
              'execution_timeout': None}}


def test_execution_table_changes(mocker, monkeypatch):
    monkeypatch.setenv("ENV_NAME", "prod")
    mocker.spy(src.handlers.table_changes, 'get_events_client')
    mocker.spy(src.lib.clients.eventbridge.boto3, 'client')
    mock_events = mocker.patch.object(src.lib.clients.eventbridge.EventsClient, 'put_event')
    execution_record_changed(EXECUTION_STREAM_EVENT, {})

    mock_events.assert_called_once()
    event = json.loads(mock_events.call_args.kwargs["detail"])
    bus_name = mock_events.call_args.kwargs["bus_name"]
    assert bus_name == "execution-changes"
    assert EXECUTION_STREAM_EVENT_EXPECTED == event


RESOURCE_RECORD_EVENT = {
    'Records': [
        {'eventID': '05c64512750bf552fe8cae304c2618f5', 'eventName': 'INSERT', 'eventVersion': '1.1',
         'eventSource': 'aws:dynamodb', 'awsRegion': 'us-east-1',
         'dynamodb': {
             'ApproximateCreationDateTime': 1670235322.0,
             'Keys': {'SK': {
                 'S': 'JIT_EVENT_ID#f00db350-fbc8-4afa-8db8-22fb71524aae#EXECUTION_ID'
                      '#62a36648-345c-4271-96e0-f66cc5e98a2f'
             },
                 'PK': {'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08'}},
             'NewImage': {'tenant_id': {
                 'S': '7ca2cba7-a783-48d2-ad5d-a15040560d08'},
                 'execution_id': {
                     'S': '62a36648-345c-4271-96e0-f66cc5e98a2f'},
                 'jit_event_id': {
                     'S': 'f00db350-fbc8-4afa-8db8-22fb71524aae'},
                 'created_at_ts': {
                     'N': '1670235322'},
                 'GSI1PK': {
                     'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08'},
                 'GSI2SK': {
                     'S': '2022-12-05T10:15:22.169877'},
                 'GSI1SK': {
                     'S': '2022-12-05T10:15:22.169877'},
                 'SK': {
                     'S': 'JIT_EVENT_ID#f00db350-fbc8-4afa-8db8-22fb71524aae#'
                          'EXECUTION_ID#62a36648-345c-4271-96e0-f66cc5e98a2f'},
                 'resource_type': {'S': 'jit'},
                 'created_at': {
                     'S': '2022-12-05T10:15:22.169877'},
                 'GSI2PK': {
                     'S': 'ITEM_TYPE#resource_in_use'},
                 'PK': {
                     'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08'}},
             'SequenceNumber': '506154300000000019579384951',
             'SizeBytes': 648,
             'StreamViewType': 'NEW_IMAGE'},
         'eventSourceARN': 'arn:aws:dynamodb:us-east-1:566740389182:table/Resources/stream/2022-12-05T04:14:44.911'}]}

RESOURCE_RECORD_EVENT_EXPECTED = {'metadata': {"env_name": "prod", 'event_id': 'f00db350-fbc8-4afa-8db8-22fb71524aae',
                                               'tenant_id': '7ca2cba7-a783-48d2-ad5d-a15040560d08',
                                               'resource_type': 'jit'},
                                  'data': {'execution_id': '62a36648-345c-4271-96e0-f66cc5e98a2f',
                                           'created_at': '2022-12-05T10:15:22.169877',
                                           'created_at_ts': 1670235322}}


def test_resource_table_resource_record(mocker, monkeypatch):
    """
    we have 2 records:
    - the counter
    - the actual record that is connected to the execution
    this tests the actual record
    :param mocker:
    :return:
    """
    monkeypatch.setenv("ENV_NAME", "prod")
    mocker.spy(src.handlers.table_changes, 'get_events_client')
    mocker.spy(src.lib.clients.eventbridge.boto3, 'client')
    mock_events = mocker.patch.object(src.lib.clients.eventbridge.EventsClient, 'put_event')
    resource_changed(RESOURCE_RECORD_EVENT, {})

    mock_events.assert_called_once()
    event = json.loads(mock_events.call_args.kwargs["detail"])
    bus_name = mock_events.call_args.kwargs["bus_name"]
    assert bus_name == "resource-changes"
    assert RESOURCE_RECORD_EVENT_EXPECTED == event


RESOURCE_COUNTER_EVENT = {
    'Records': [{'eventID': '39810b5d8c522e8166ee712f1882014d', 'eventName': 'MODIFY', 'eventVersion': '1.1',
                 'eventSource': 'aws:dynamodb', 'awsRegion': 'us-east-1',
                 'dynamodb': {
                     'ApproximateCreationDateTime': 1670235322.0,
                     'Keys': {'SK': {'S': 'RESOURCE_TYPE#jit'},
                              'PK': {
                                  'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08'}},
                     'NewImage': {'tenant_id': {'S': '7ca2cba7-a783-48d2-ad5d-a15040560d08'},
                                  'resources_in_use': {'N': '9'}, 'max_resources_in_use': {'N': '10'},
                                  'SK': {'S': 'RESOURCE_TYPE#jit'}, 'resource_type': {'S': 'jit'},
                                  'PK': {'S': 'TENANT#7ca2cba7-a783-48d2-ad5d-a15040560d08'}},
                     'SequenceNumber': '506154200000000019579384944', 'SizeBytes': 229,
                     'StreamViewType': 'NEW_IMAGE'},
                 'eventSourceARN': 'arn:aws:dynamodb:us-east-1:566740389182:table/'
                                   'Resources/stream/2022-12-05T04:14:44.911'}]}

RESOURCE_COUNTER_EVENT_EXPECTED = {
    'metadata': {"env_name": "prod", 'tenant_id': '7ca2cba7-a783-48d2-ad5d-a15040560d08', 'resource_type': 'jit'},
    'data': {'resources_in_use': 9, 'max_resources_in_use': 10}
}


def test_resource_table_resource_counter(mocker, monkeypatch):
    """
    we have 2 records:
    - the counter
    - the actual record that is connected to the execution
    this tests the counter record
    :param mocker:
    :return:
    """
    monkeypatch.setenv("ENV_NAME", "prod")
    mocker.spy(src.handlers.table_changes, 'get_events_client')
    mocker.spy(src.lib.clients.eventbridge.boto3, 'client')
    mock_events = mocker.patch.object(src.lib.clients.eventbridge.EventsClient, 'put_event')
    resource_changed(RESOURCE_COUNTER_EVENT, {})

    mock_events.assert_called_once()
    bus_name = mock_events.call_args.kwargs["bus_name"]
    assert bus_name == "resource-changes"
    event = json.loads(mock_events.call_args.kwargs["detail"])
    assert RESOURCE_COUNTER_EVENT_EXPECTED == event
