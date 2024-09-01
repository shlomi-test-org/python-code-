def mock_get_ssm_param(mocker):
    mocked_connection_string = 'https://api.dummy.mongo'
    mocker.patch("src.lib.data.mongo.utils.get_ssm_param", return_value=mocked_connection_string)
    mocker.patch("src.lib.clients.s3.get_aws_config", return_value={"region_name": "us-east-1"})
    return mocked_connection_string
