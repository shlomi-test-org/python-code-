import datetime
import uuid
from typing import List, Dict, Union, Optional

from jit_utils.models.findings.entities import Resolution, Ticket
from jit_utils.models.ignore_rule.entities import FieldToBeIgnoredBy

from src.lib.models.finding_model import UiResolution
from jit_utils.models.tags.entities import Tag
from src.lib.data.mongo.constants import SPECS_KEY, SPECS_VALUE


def build_ignore_rule_dict(tenant_id: str = str(uuid.uuid4()),
                           ignore_rule_id: str = "e6390f00-19ac-4a6e-9f4a-c0616cb94528",
                           type: str = "ignore",
                           asset_id: str = "6d50c3df-4ae5-468e-85af-b13444afae0a",
                           control_name: str = "github-branch-protection",
                           created_at: str = None,
                           fingerprint: str = "49863a0c0b5b6490f9f02e776f9bc1c",
                           comment: str = "",
                           source: str = "api",
                           reason: str = "accept_risk",
                           fields: [List[Dict]] = None
                           ):
    if not fields:
        fields = [
            FieldToBeIgnoredBy(
                name="fingerprint",
                value=fingerprint
            ).dict(),
            FieldToBeIgnoredBy(
                name="control_name",
                value=control_name
            ).dict(),
            FieldToBeIgnoredBy(
                name="asset_id",
                value=asset_id
            ).dict()
        ]
    return {
        "_id": ignore_rule_id,
        "id": ignore_rule_id,
        "tenant_id": tenant_id,
        "type": type,
        "created_at": created_at,
        "modified_at": created_at,
        "comment": comment,
        "reason": reason,
        "fields": fields,
        "source": source,
        "user_email": "",
        "user_id": "",
        "user_name": None,
    }


def build_finding_dict(
        tenant_id: str = str(uuid.uuid4()),
        asset_id: str = str(uuid.uuid4()),
        asset_name: str = "my-asset-name",
        filename: str = None,
        workflow_suite_id: str = str(uuid.uuid4()),
        finding_id: str = None,
        workflow_id: str = "my-workflow-id",
        jit_event_id: str = "my-event-id",
        jit_event_name: str = "item_activated",
        first_jit_event_name: str = "first-event-name",
        execution_id: str = "execution-id",
        created_at: str = None,
        should_modified_at_add_5_minutes: bool = False,
        fingerprint: str = "dummy-fingerprint",
        control_name: str = "kick",
        pr_number: str = "1",
        is_code_finding: bool = True,
        issue_severity: str = "LOW",
        vulnerability_type: str = "code_vulnerability",
        asset_type: str = None,
        plan_layer: str = 'code',
        plan_item: str = 'dummy-plan-item',
        plan_items: List[str] = None,
        location_text: str = None,
        location: Optional[str] = 'https://github.com/jitsecurity/github-service/blob/main/input/'
                                  'bandit/passwords/password.py#L1-L1',
        resolution: Union[Resolution, UiResolution] = Resolution.OPEN,
        test_name: str = 'hardcoded_password_string',
        backlog: bool = False,
        branch: str = 'my-branch',
        with_specs: bool = False,
        ignored: bool = False,
        ignore_rules_ids: List[str] = [],
        fixed_at_execution_id: str = None,
        fix_suggestion: Optional[Dict] = {"source": "control"},
        tags: List[Tag] = [],
        issue_text: str = "Possible hardcoded password: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'",
        test_id: str = "B105",
        old_fingerprints: List[str] = [],
        jobs: List[Dict] = [{'workflow_slug': "workflow-slug", 'job_name': "job-name"}],
        scan_scope: dict = {},
        priority_factors: List[str] = [],
        priority_score: int = 0,
        asset_priority_score: int = 0,
        tickets: List[Ticket] = [],
        modified_at: str = None,
        fix_pr_url: str = None,
) -> Dict:
    plan_items = plan_items or [plan_item]
    asset_type = asset_type or 'repo' if is_code_finding else 'aws_account'
    if created_at is None:
        created_at = str(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f"))
    if modified_at is None:
        modified_at = created_at
    if should_modified_at_add_5_minutes:
        dt = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%f") + datetime.timedelta(minutes=5)
        modified_at = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")

    if not finding_id:
        finding_id = str(uuid.uuid4())
    location = location
    finding = {
        'id': finding_id,
        'created_at': created_at,
        'tenant_id': tenant_id,
        'asset_id': asset_id,
        'asset_type': asset_type,
        'asset_name': asset_name,
        'workflow_suite_id': workflow_suite_id,
        'first_workflow_suite_id': workflow_suite_id,
        'workflow_id': workflow_id,
        'first_workflow_id': workflow_id,
        'jit_event_id': jit_event_id,
        'jit_event_name': jit_event_name,
        'first_jit_event_name': first_jit_event_name,
        'fix_suggestion': fix_suggestion,
        'execution_id': execution_id,
        'job_name': 'my-job-name',
        'control_name': control_name,
        'status': 'FAIL',
        'test_name': test_name,
        'fingerprint': fingerprint,
        'test_id': test_id,
        'issue_text': issue_text,
        'issue_confidence': 'MEDIUM',
        'issue_severity': issue_severity,
        'location': location,
        'references': [
            {
                'url': 'https://bandit.readthedocs.io/en/latest/plugins/b105_hardcoded_password_string.html',
                'name': 'https://bandit.readthedocs.io/en/latest/plugins/b105_hardcoded_password_string.html'
            }
        ],
        'state': 'TO_VERIFY',
        'resolution': resolution,
        'plan_layer': plan_layer,
        'plan_item': plan_item,
        'plan_items': plan_items,
        'vulnerability_type': vulnerability_type,
        'modified_at': modified_at,
        'last_detected_at': created_at,
        'vendor': 'github' if is_code_finding else 'aws',
        'backlog': backlog,
        '_id': finding_id,
        'ignored': ignored,
        'ignore_rules_ids': ignore_rules_ids,
        'fixed_at_execution_id': fixed_at_execution_id,
        'tags': [tag.dict() for tag in tags],
        'old_fingerprints': old_fingerprints,
        'jobs': jobs,
        'scan_scope': scan_scope,
        'priority_factors': priority_factors,
        'priority_score': priority_score,
        'asset_priority_score': asset_priority_score,
        'tickets': [ticket.dict() for ticket in tickets],
        'fix_pr_url': fix_pr_url,
    }
    if is_code_finding:
        if not filename:
            filename = "/code/passwords/password.py"
        asset_name = 'repo-name'
        finding['filename'] = filename
        finding['asset_domain'] = 'org-name'
        finding['location_text'] = location_text or 'org-name/repo-name'
        finding['code_attributes'] = {
            'branch': branch,
            'filename': filename,
            'line_range': '1-1',
            'user_vendor_name': 'my-name',
            'code_snippet': "1 EXAMPLE_SECRET = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'\n2\n"
        }
        finding['scan_scope'] = {**finding['scan_scope'], 'branch': branch}
        if pr_number:
            finding['code_attributes']['pr_number'] = pr_number
            finding['scan_scope'] = {**finding['scan_scope'], 'pr_number': pr_number}
    else:
        asset_name = "aws-asset"
        finding['asset_domain'] = 'aws-domain'
        finding['location_text'] = location_text or 'aws-asset/aws-domain'

    finding['asset_name'] = asset_name

    if with_specs:
        finding = sync_specs_on_finding(finding)
    return finding


def sync_specs_on_finding(finding: Dict):
    team_specs = [{SPECS_KEY: team_tag["name"], SPECS_VALUE: team_tag["value"]} for team_tag in finding['tags']]
    plan_items_specs = [{SPECS_KEY: "plan_items", SPECS_VALUE: p_i} for p_i in finding['plan_items']]
    if 'code_attributes' in finding:
        filename = finding['code_attributes']['filename']
    else:
        filename = None
    finding['specs'] = [
        {"k": "ignored", "v": finding['ignored']},
        {"k": "asset_type", "v": finding['asset_type']},
        {"k": "resolution", "v": finding['resolution']},
        {"k": "plan_layer", "v": finding['plan_layer']},
        {"k": "issue_severity", "v": finding['issue_severity']},
        {"k": "vulnerability_type", "v": finding['vulnerability_type']},
        {"k": "control_name", "v": finding['control_name']},
        {"k": "asset_name", "v": finding['asset_name']},
        {"k": "test_name", "v": finding['test_name']},
        {"k": "location", "v": finding['location']},
        {"k": "location_text", "v": finding['location_text']},
        {"k": "created_at", "v": finding['created_at']},
        *team_specs,
        {"k": "filename", "v": filename},
        *plan_items_specs,
    ]
    return finding


def get_saved_filter_sample(tenant_id: str):
    return [
        {
            'id': str(uuid.uuid4()),
            'tenant_id': tenant_id,
            'name': 'some-filter',
            'description': 'desc',
            'is_default': False,
            'created_at': 'now',
            'filters': [
                {
                    "key": "time_ago",
                    "type": "single_select",
                    "valueOptions": [
                        "ONE_WEEK",
                        "TWO_WEEKS",
                        "ONE_MONTH"
                    ],
                    "selectedValue": "ONE_MONTH",
                    "defaultValue": "ONE_MONTH",
                    "isVisible": False,
                    "defaultVisibility": True
                },
                {
                    "key": "resolution",
                    "type": "multi_select",
                    "valueOptions": [
                        "OPEN",
                        "FIXED",
                        "IGNORED"
                    ],
                    "selectedValue": [
                        "OPEN"
                    ],
                    "defaultValue": [
                        "OPEN"
                    ],
                    "isVisible": False,
                    "defaultVisibility": True
                },
            ]
        },
        {
            'id': str(uuid.uuid4()),
            'tenant_id': tenant_id,
            'name': 'name2',
            'description': 'desc',
            'is_default': False,
            'created_at': 'now',
            'filters': [
                {
                    "key": "time_ago",
                    "type": "single_select",
                    "valueOptions": [
                        "ONE_WEEK",
                        "TWO_WEEKS",
                        "ONE_MONTH"
                    ],
                    "selectedValue": "ONE_MONTH",
                    "defaultValue": "ONE_MONTH",
                    "isVisible": True,
                    "defaultVisibility": True
                },
                {
                    "key": "resolution",
                    "type": "multi_select",
                    "valueOptions": [
                        "OPEN",
                        "FIXED",
                        "IGNORED"
                    ],
                    "selectedValue": [
                        "OPEN"
                    ],
                    "defaultValue": [
                        "OPEN"
                    ],
                    "isVisible": False,
                    "defaultVisibility": True
                },
            ]
        },
        {
            'id': str(uuid.uuid4()),
            'tenant_id': tenant_id,
            'name': 'name3',
            'description': 'desc',
            'is_default': True,
            'created_at': 'now',
            'filters': [
                {
                    "key": "time_ago",
                    "type": "single_select",
                    "valueOptions": [
                        "ONE_WEEK",
                        "TWO_WEEKS",
                        "ONE_MONTH"
                    ],
                    "selectedValue": "ONE_MONTH",
                    "defaultValue": "ONE_MONTH",
                    "isVisible": True,
                    "defaultVisibility": True
                },
                {
                    "key": "resolution",
                    "type": "multi_select",
                    "valueOptions": [
                        "OPEN",
                        "FIXED",
                        "IGNORED"
                    ],
                    "selectedValue": [
                        "OPEN"
                    ],
                    "defaultValue": [
                        "OPEN"
                    ],
                    "isVisible": True,
                    "defaultVisibility": True
                },
            ]
        }
    ]
