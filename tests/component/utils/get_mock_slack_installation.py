def get_mock_slack_installation(tenant_id='my-tenant-id'):
    return {
        'tenant_id': tenant_id,
        'app_id': 'app_id',
        'owner': 'owner',
        'installation_id': 'installation_id',
        'vendor_response': {'incoming_webhook': {'url': 'https://webhook_url.com'}}
    }
