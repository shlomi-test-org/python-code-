import pydantic
import pytest

from src.lib.clients.plan_service_models import AwsApplicationConfiguration


def test_create_aws_configuration_model():
    aws_config = AwsApplicationConfiguration(
        type="aws_configuration", application_name="app1", account_ids=["123456789012"]
    )

    assert aws_config is not None
    assert aws_config.type == "aws_configuration"


def test_create_aws_configuration_model_validator_with_invalid_account_id():
    with pytest.raises(Exception) as value_error:
        AwsApplicationConfiguration(
            type="aws_configuration", application_name="app1", account_ids=["12345672"]
        )

    assert "account_ids must consist of 12 digits only" in str(value_error.value)
    assert value_error.type == pydantic.error_wrappers.ValidationError


def test_create_aws_configuration_model_validator_with_empty_list():
    with pytest.raises(Exception) as value_error:
        AwsApplicationConfiguration(type="aws_configuration", application_name="app1", account_ids=[])

    assert "account_ids cannot be empty" in str(value_error.value)
    assert value_error.type == pydantic.error_wrappers.ValidationError
