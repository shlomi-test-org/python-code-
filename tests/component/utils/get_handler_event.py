import json
from typing import List, Union, Dict


def get_handler_event(body: Union[Dict, List] = {}, path_parameters={},
                      tenant_id='19881e72-6d3b-49df-b79f-298ad89b8056',
                      token=None, query_string_parameters={}, headers={}, permissions=None,
                      email=None, user_id=None, event_type=None):
    event = {
        'httpMethod': 'GET',
        'pathParameters': path_parameters,
        'queryStringParameters': query_string_parameters,
        'requestContext': {
            'authorizer': {
                'tenant_id': tenant_id,
                'token': token,
                'permissions': permissions or [],
            }
        },
        'headers': headers,
        'body': json.dumps(body),
        'detail': {
            'body': body,
            'tenant_id': tenant_id,
            'event_type': event_type
        },
    }
    # We add email and user id separately because we want them to not exist at all if they are None.
    if email:
        event['requestContext']['authorizer']['frontegg_user_email'] = email
    if user_id:
        event['requestContext']['authorizer']['frontegg_user_id'] = user_id
    return event
