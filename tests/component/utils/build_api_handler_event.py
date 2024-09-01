def build_api_handler_event(tenant_id: str, path_parameters: dict = None, body: dict = None):
    return {
        'httpMethod': 'POST',
        'requestContext': {
            'authorizer': {
                'tenant_id': tenant_id,
            }
        },
        'pathParameters': path_parameters or {},
        'body': body or {},
    }
