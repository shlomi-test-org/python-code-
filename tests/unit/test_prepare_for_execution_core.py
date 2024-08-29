from typing import Dict, List, Optional

import pytest
from jit_utils.event_models.trigger_event import TriggerScheme
from jit_utils.models.asset.entities import AssetStatus
from pytest_mock import MockerFixture

from src.lib.constants import ASSET_TYPE
from src.lib.cores.prepare_for_execution_core import (
    _send_trigger_scheme_bulk_events,
    _create_asset_trigger_scheme,
    _get_event_trigger_scheme,
    _split_event_trigger_scheme_by_asset,
    _get_filtered_assets,
    parse_condition,
    _should_run_job_by_enriched_data,
)
from src.lib.models.asset import Asset
from src.lib.models.trigger import JobTemplateWrapper
from tests.common import (
    InstallationFactory,
    JitEventFactory,
    FilteredJobFactory,
    AssetFactory,
)

TRIGGER_SCHEME_ASSET: Asset = AssetFactory.build(
    asset_id="asset-1", asset_name="asset-1", asset_type="repo", vendor="vendor-1", owner="owner-1"
)

TRIGGER_SCHEME_FILTERED_JOBS = FilteredJobFactory.batch(
    size=2,
    workflow_template={
        "slug": "workflow-sast",
        "name": "SAST Workflow",
        "type": "workflow",
        "default": True,
        "content": "jobs:\n  static-code-analysis-go:\n    asset_type: repo\n    default: true\n    if:\n     ",
        "depends_on": [
            "workflow-enrichment-code"
        ],
        "params": None,
        "plan_item_template_slug": None,
        "asset_types": [
            "repo",
            "repo",
        ]
    },
    raw_job_template={
        ASSET_TYPE: "repo",
        "runner": "github_actions",
        "steps": [
            {
                "name": "Run Go",
                "uses": "ghcr.io/jitsecurity-controls/control-gosec-alpine:main",
                "params": {
                    "args": "-fmt=json -severity=high \\${WORK_DIR:-.}/..."
                }
            }
        ],

    },
)

TRIGGER_SCHEME_INSTALLATIONS = {
    ("vendor-1", "owner-1"): InstallationFactory.build(),
    ("vendor-1", "owner-2"): InstallationFactory.build(),
    ("vendor-2", "owner-1"): InstallationFactory.build(),
    ("vendor-2", "owner-2"): InstallationFactory.build(),
}


def get_assets() -> List[Dict]:
    return [
        AssetFactory.build(asset_name="asset", asset_id="123", asset_type="repo"),
        AssetFactory.build(asset_name="asset", asset_id="123", asset_type="aws_account", status=AssetStatus.CONNECTED),
        AssetFactory.build(asset_name="asset", asset_id="123", asset_type="api", target_url="/path/to/swagger.yaml"),
        AssetFactory.build(asset_name="asset", asset_id="123", asset_type="web", target_url="http://example.com"),
    ]


@pytest.mark.parametrize("assets, filtered_jobs, expected_assets_amount", [
    (AssetFactory.batch(size=5, asset_type="repo"),
     [FilteredJobFactory.build(raw_job_template={ASSET_TYPE: "repo"})],
     5),
    (AssetFactory.batch(size=5, asset_type="repo"),
     FilteredJobFactory.batch(size=2, raw_job_template={ASSET_TYPE: "repo"}),
     5),
    (AssetFactory.batch(size=2, asset_type="repo") + AssetFactory.batch(size=2, asset_type="aws_account",
                                                                        status=AssetStatus.CONNECTED),
     FilteredJobFactory.batch(size=2, raw_job_template={ASSET_TYPE: "repo"}),
     2)
])
def test_get_filtered_assets(
        assets: List[Asset], filtered_jobs: List[JobTemplateWrapper],
        expected_assets_amount
) -> None:
    filtered_assets = _get_filtered_assets(assets, filtered_jobs)
    assert len(filtered_assets) == expected_assets_amount


@pytest.mark.parametrize("condition, expected_result", [
    ("'pulumi' in ${{ event.metadata.frameworks }}", ("pulumi", "frameworks")),
    ("'pulumi' in event.metadata.languages", None),
    ("'pulumi' in ${{ event.languages }}", None)
])
def test_parse_condition(condition: str, expected_result: Optional[str]) -> None:
    assert parse_condition(condition) == expected_result


@pytest.mark.parametrize(
    "installations,expected_result",
    [
        ({}, None),
        ({("vendor_1", "owner_1"): InstallationFactory.build(installation_id="id-1")}, None),
        (
                {
                    ("vendor_1", "owner_1"): InstallationFactory.build(installation_id="id-1"),
                    ("id123", "jit"): InstallationFactory.build(installation_id="id-2"),
                },
                "id-2",
        ),
    ],
)
def test__create_asset_trigger_scheme(installations: Dict, expected_result: Optional[str]) -> None:
    asset: Asset = AssetFactory.build(
        asset_name="asset", asset_id="123", asset_type="repo", owner="jit", vendor="id123"
    )

    result = _create_asset_trigger_scheme(asset, installations.get((asset.vendor, asset.owner)))
    assert result.asset_id == asset.asset_id
    assert result.installation_id == expected_result


def test__get_event_trigger_scheme() -> None:
    result = _get_event_trigger_scheme(
        TRIGGER_SCHEME_FILTERED_JOBS,
        TRIGGER_SCHEME_ASSET,
        TRIGGER_SCHEME_INSTALLATIONS[(TRIGGER_SCHEME_ASSET.vendor, TRIGGER_SCHEME_ASSET.owner)],
    )

    assert result.amount_of_triggered_jobs == 2


def test__split_event_trigger_scheme_by_asset() -> None:
    event_execution_scheme = _get_event_trigger_scheme(
        TRIGGER_SCHEME_FILTERED_JOBS,
        TRIGGER_SCHEME_ASSET,
        TRIGGER_SCHEME_INSTALLATIONS[(TRIGGER_SCHEME_ASSET.vendor, TRIGGER_SCHEME_ASSET.owner)],
    )
    trigger_scheme_events_result = _split_event_trigger_scheme_by_asset(
        event_execution_scheme, [TRIGGER_SCHEME_ASSET]
    )

    assert len(trigger_scheme_events_result) == 1
    assert event_execution_scheme.amount_of_triggered_jobs == 2


TRIGGER_SCHEME = _get_event_trigger_scheme(
    TRIGGER_SCHEME_FILTERED_JOBS,
    TRIGGER_SCHEME_ASSET,
    TRIGGER_SCHEME_INSTALLATIONS[(TRIGGER_SCHEME_ASSET.vendor, TRIGGER_SCHEME_ASSET.owner)],
)


@pytest.mark.parametrize("trigger_schemes_amount", [0, 1, 5, 40, 100])
def test__send_trigger_scheme_bulk_events(mocker: MockerFixture, trigger_schemes_amount: int) -> None:
    event_execution_scheme = _get_event_trigger_scheme(
        TRIGGER_SCHEME_FILTERED_JOBS,
        TRIGGER_SCHEME_ASSET,
        TRIGGER_SCHEME_INSTALLATIONS[(TRIGGER_SCHEME_ASSET.vendor, TRIGGER_SCHEME_ASSET.owner)],
    )

    jit_event = JitEventFactory.build()

    trigger_scheme = TriggerScheme(event_execution_scheme=event_execution_scheme, jit_event=jit_event)

    multiple_trigger_schemes = [trigger_scheme for _ in range(trigger_schemes_amount)]

    mocked__send_trigger_scheme_event = mocker.patch(
        "src.lib.cores.prepare_for_execution_core.send_trigger_scheme_event", return_value=None
    )

    _send_trigger_scheme_bulk_events(jit_event, multiple_trigger_schemes)

    assert mocked__send_trigger_scheme_event.called == bool(trigger_schemes_amount)


@pytest.mark.parametrize("if_condition, enriched_data, expected_result", [
    ({"frameworks": ["pulumi"], "languages": ["python"]}, {"frameworks": ["pulumi"], "languages": ["python"]}, True),
    ({"languages": ["python"]}, {"frameworks": ["pulumi"], "languages": ["python"]}, True),
    ({"frameworks": ["pulumi"]}, {"frameworks": ["pulumi"], "languages": ["python"]}, True),
    ({"frameworks": ["pulumi"], "languages": ["python"]}, {"languages": ["python"]}, True),
    ({"frameworks": ["pulumi"], "languages": ["python"]}, {"frameworks": ["pulumi"]}, True),
    ({"languages": ["python", "go", "js"]}, {"languages": ["python"]}, True),
    ({"languages": ["python"]}, {"languages": ["python", "go", "js"]}, True),
    ({"frameworks": ["pulumi", "laravel", "angular"]}, {"frameworks": ["pulumi"]}, True),
    ({"frameworks": ["pulumi"]}, {"frameworks": ["pulumi", "laravel", "angular"]}, True),
    ({}, {"frameworks": ["pulumi"], "languages": ["python"]}, True),
    ({}, {}, True),
    ({"frameworks": ["pulumi"], "languages": ["python"]}, {}, True),
    ({"frameworks": ["pulumi"], "languages": ["python"]}, {"frameworks": [], "languages": []}, False),
    ({"frameworks": ["laravel"], "languages": ["ruby"]}, {"frameworks": ["pulumi"], "languages": ["python"]}, False),
    ({"frameworks": ["laravel"]}, {"frameworks": ["pulumi"], "languages": ["python"]}, False),
    ({"languages": ["ruby"]}, {"frameworks": ["pulumi"], "languages": ["python"]}, False),
    ({"woot": ["boot"]}, {"frameworks": ["pulumi"], "languages": ["python"]}, False),
    ({"frameworks": ["pulumi"], "languages": ["python"]}, {"woot": ["boot"]}, False),
    ({"languages": ["python", "go", "js"]}, {"languages": ["rust"]}, False),
    ({"languages": ["rust"]}, {"languages": ["python", "go", "js"]}, False),
    ({"frameworks": ["pulumi", "laravel", "angular"]}, {"frameworks": ["tf"]}, False),
    ({"frameworks": ["tf"]}, {"frameworks": ["pulumi", "laravel", "angular"]}, False),
])
def test_should_run_job_by_enriched_data(if_condition, enriched_data, expected_result) -> None:
    raw_job_template_mock = {
        "if": if_condition,
        "asset_type": "repo",
        "runner": "github_actions",
        "steps": [
            {
                "name": "Run Bandit",
                "with": {
                    "args": "-r \\${WORK_DIR:-.} -f json -q -lll -iii"
                },
                "uses": "ghcr.io/jitsecurity-controls/control-bandit-slim:latest",
                "tags": {
                    "security_tool": "Bandit",
                    "links": {
                        "security_tool": "https://github.com/PyCQA/bandit",
                        "github": "https://github.com/jitsecurity-controls/jit-python-code-scanning-control"
                    }
                }
            }
        ],
        "tags": {
            "languages": [
                "python"
            ]
        }
    }

    assert _should_run_job_by_enriched_data(raw_job_template_mock, enriched_data) is expected_result
