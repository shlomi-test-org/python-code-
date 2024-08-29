import uuid
from typing import Dict, Optional, List

from jit_utils.models.ignore_rule.entities import FieldToBeIgnoredBy, IgnoreRule, OperatorTypes
from jit_utils.models.ignore_rule.requests import CreateIgnoreRuleRequest

from src.lib.constants import PLAN_ITEMS


def get_create_fingerprint_ignore_rule_payload(type: str = "ignore",
                                               asset_id: str = "6d50c3df-4ae5-468e-85af-b13444afae0a",
                                               control_name: str = "github-branch-protection",
                                               fingerprint: str = "49863a0c0b5b6490f9f02e776f9bc1c",
                                               comment: str = "",
                                               reason: str = "accept_risk",
                                               user_name: Optional[str] = None) -> Dict:
    return CreateIgnoreRuleRequest(
        type=type,
        asset_id=asset_id,
        comment=comment,
        reason=reason,
        user_name=user_name,
        fields=[
            FieldToBeIgnoredBy(name="fingerprint", value=fingerprint),
            FieldToBeIgnoredBy(name="control_name", value=control_name),
            FieldToBeIgnoredBy(name="asset_id", value=asset_id)
        ]
    ).dict()


def build_fingerprint_ignore_rule_dict(tenant_id="19881e72-6d3b-49df-b79f-298ad89b8056",
                                       ignore_rule_id=str(uuid.uuid4()),
                                       asset_id="6d50c3df-4ae5-468e-85af-b13444afae0a", control_name="kics",
                                       fingerprint="49863a0c0b5b6490f9f02e776f9bc1c",
                                       modified_at="2022-01-14T00:00:00") -> Dict:
    return IgnoreRule(
        id=ignore_rule_id,
        created_at="2022-01-14T00:00:00",
        tenant_id=tenant_id,
        type="ignore",
        comment="",
        reason="accept_risk",
        modified_at=modified_at,
        fields=[
            FieldToBeIgnoredBy(name="fingerprint", value=fingerprint),
            FieldToBeIgnoredBy(name="control_name", value=control_name),
            FieldToBeIgnoredBy(name="asset_id", value=asset_id)
        ]

    ).dict()


def build_asset_id_ignore_rule_dict(tenant_id="19881e72-6d3b-49df-b79f-298ad89b8056",
                                    asset_id="6d50c3df-4ae5-468e-85af-b13444afae0a",
                                    modified_at="2022-01-14T00:00:00") -> Dict:
    return IgnoreRule(
        id=str(uuid.uuid4()),
        created_at="2022-01-14T00:00:00",
        modified_at=modified_at,
        tenant_id=tenant_id,
        type="exclude",
        comment="",
        reason="accept_risk",
        fields=[
            FieldToBeIgnoredBy(name="asset_id", value=asset_id),
        ]

    ).dict()


def build_plan_item_ignore_rule_dict(tenant_id: str, plan_items: List[str]) -> Dict:
    return IgnoreRule(
        id=str(uuid.uuid4()),
        created_at="2023-01-01T00:00:00",
        tenant_id=tenant_id,
        type="exclude",
        comment="Ignoring specific plan item",
        reason="accept_risk",
        fields=[
            FieldToBeIgnoredBy(name="plan_items", value=plan_items)
        ]
    ).dict()


def build_ignore_rule_dict_by_fields(tenant_id: str, fields: List[FieldToBeIgnoredBy]) -> Dict:
    return IgnoreRule(
        id=str(uuid.uuid4()),
        created_at="2023-01-01T00:00:00",
        tenant_id=tenant_id,
        type="exclude",
        comment="",
        reason="accept_risk",
        fields=fields
    ).dict()


def build_filename_ignore_rule_dict(tenant_id: str, filename_regex: str) -> Dict:
    return IgnoreRule(
        id=str(uuid.uuid4()),
        created_at="2023-01-01T00:00:00",
        tenant_id=tenant_id,
        type="exclude",
        comment="Ignoring specific filename pattern",
        reason="accept_risk",
        fields=[
            FieldToBeIgnoredBy(name="filename", value=filename_regex, operator=OperatorTypes.REGEX)
        ]
    ).dict()


def build_plan_items_ignore_rule_dict(tenant_id: str, plan_items: List[str],
                                      modified_at: str = "2022-01-14T00:00:00") -> Dict:
    return IgnoreRule(
        id=str(uuid.uuid4()),
        created_at="2023-01-01T00:00:00",
        modified_at=modified_at,
        tenant_id=tenant_id,
        type="exclude",
        comment="Ignoring specific filename pattern",
        fields=[
            FieldToBeIgnoredBy(name=PLAN_ITEMS, value=plan_items, operator=OperatorTypes.CONTAINED)
        ]
    ).dict()


def assert_ignore_rule(ignore_rule: Dict, id: str, fingerprint: str, tenant_id: str):
    assert ignore_rule['id'] == id
    assert ignore_rule['tenant_id'] == tenant_id
    # get the nested fingerprint field in ignore rule fields
    for field in ignore_rule['fields']:
        if field['name'] == 'fingerprint':
            assert field['value'] == fingerprint
