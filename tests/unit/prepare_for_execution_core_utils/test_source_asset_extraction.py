import pytest
from pydantic import ValidationError

from src.lib.cores.prepare_for_execution_core_utils.source_asset_extraction import (
    _get_source_resource_from_code_related_jit_event,
    _get_source_resource_from_deployment_jit_event,
    extract_source_asset_from_event
)
from tests.common import CodeRelatedJitEventFactory, DeploymentJitEventFactory, TriggerScheduledTaskJitEventFactory


@pytest.mark.parametrize(
    'jit_event,should_succeed',
    [
        (CodeRelatedJitEventFactory.build(asset_id='id-1', owner='jit', vendor='github'), True),
        (CodeRelatedJitEventFactory.build(asset_id=None), False),
    ]
)
def test__get_source_resource_from_code_related_jit_event(jit_event, should_succeed):
    if should_succeed:
        source_asset = _get_source_resource_from_code_related_jit_event(jit_event)
        assert source_asset
    else:
        with pytest.raises(ValidationError):
            _get_source_resource_from_code_related_jit_event(jit_event)


@pytest.mark.parametrize(
    'jit_event,should_succeed',
    [
        (DeploymentJitEventFactory.build(asset_id='id-1', owner='jit', vendor='github'), True),
        (DeploymentJitEventFactory.build(asset_id=None), False),
    ]
)
def test__get_source_resource_from_deployment_jit_event(jit_event, should_succeed):
    if should_succeed:
        source_asset = _get_source_resource_from_deployment_jit_event(jit_event)
        assert source_asset
    else:
        with pytest.raises(ValidationError):
            _get_source_resource_from_deployment_jit_event(jit_event)


def test_extract_source_asset_from_event_jit_event_without_source_asset():
    jit_event = TriggerScheduledTaskJitEventFactory.build(cron_expression='* * * * *', single_execution_time=None)
    source_asset = extract_source_asset_from_event(jit_event)
    assert source_asset is None


@pytest.mark.parametrize('jit_event', [
    CodeRelatedJitEventFactory.build(asset_id='id-1', owner='jit', vendor='github'),
    DeploymentJitEventFactory.build(asset_id='id-2', owner='jit', vendor='github'),
])
def test_extract_source_asset_from_event_jit_event_with_source_asset(jit_event):
    source_asset = extract_source_asset_from_event(jit_event)
    assert source_asset
