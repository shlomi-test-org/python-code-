from src.lib.models.finding_model import Finding


def finding_dict_to_mongo_record(finding: dict):
    return {
        **Finding(**finding).dict(),
        '_id': finding['id'],
        'specs': [
            {"k": "asset_type", "v": finding['asset_type']},
            {
                "k": "resolution",
                "v": finding['resolution'] if isinstance(finding['resolution'], str) else finding['resolution'].value
            },
            {"k": "plan_layer", "v": finding['plan_layer']},
            {"k": "issue_severity", "v": finding['issue_severity']},
            {"k": "vulnerability_type", "v": finding['vulnerability_type']},
            {"k": "plan_item", "v": finding['plan_item']},
            {"k": "control_name", "v": finding['control_name']},
            {"k": "asset_name", "v": finding['asset_name']},
            {"k": "test_name", "v": finding['test_name']},
            {"k": "location", "v": finding['location']},
            {"k": "location_text", "v": finding['location_text']},
            {"k": "created_at", "v": finding['created_at']},
        ]
    }
