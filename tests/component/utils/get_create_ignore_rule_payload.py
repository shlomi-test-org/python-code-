from typing import Dict


def get_create_ignore_rule_payload(tenant_id='tenant_id', finding_id='5c481b2c-aaf1-4289-b2ac-3ddc79bc0196',
                                   asset_id='5c481b2c-1234-4289-b2ac-3ddc79bc0196', fingerprint='fingerprint',
                                   id='9f804eb58f264c1e95341cb262a70d2b'):
    return {
        "owner": "myGhUser",
        "tenant_id": tenant_id,
        "id": id,
        "related_finding_id": finding_id,
        "control": "trivy",
        "branch_name": "update_pyversion_numpy",
        "is_active": True,
        "comment": "comment",
        "pull_request_number": None,
        "added_by": "myGHUser",
        "created_at": "2023-01-22T09:51:11.334356",
        "reason": "false_positive",
        "vendor": "github",
        "asset_id": asset_id,
        "comment_url": None,
        "scope": "repo",
        "origin_reference": "https://github.com/myOrg/myRepo/pull/19#discussion_r1083421610",
        "rule_content": "ad0ebe67240acfa09b979ef5ebeee679ad8d59a460627b33cd88eada7df8f7ba",
        "fingerprint": fingerprint,
        "modified_at": "2023-01-22T09:51:11.334356",
        "type": "fingerprint",
        "file_path": "Dockerfile"
    }


def get_ignore_rule_db_item(tenant_id: str, ignore_rule_id: str, asset_id: str, created_at: str,
                            ignore_rule_payload: Dict):
    return {
        **ignore_rule_payload,
        'PK': f'TENANT#{tenant_id}',
        'SK': f'ID#{ignore_rule_id}',
        'GSI1PK': f'TENANT#{tenant_id}',
        'GSI1SK': f'CREATED_AT#{created_at}',
        'GSI2SK': 'VENDOR#github#OWNER#myGhUser#SCOPE#repo#ASSET_ID#'
                  f'{asset_id}#CONTROL#trivy#ID#{ignore_rule_id}',
        'created_at': created_at,
        'modified_at': created_at,
        'id': ignore_rule_id,
    }
