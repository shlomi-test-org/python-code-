import json
import os
import sys
from typing import Dict

sys.path.append(os.getcwd())
from src.main import add_fix_suggestions_where_possible

required_fixes = [
    {
        "file_name": "tests/unit/remediation/redshift-cluster.tf",
        "fix_suggestion": {
            "start_line": 17,
            "end_line": 17,
            "guidelines": "**Issue Type**: IncorrectValue\n**Expected value**: aws_redshift_cluster.encrypted should be"
                          " set to false\n**Actual value**: aws_redshift_cluster.encrypted is true",
            "title": "Redshift Not Encrypted",
            "reason": "Encryption - AWS Redshift Cluster should be encrypted. Check if 'encrypted' field is false or"
                      " undefined (default is false). ",
            "filename": "tests/unit/remediation/redshift-cluster.tf",
            "current_text": "  encrypted          = false",
            "new_text": "  encrypted          = true",
            "is_auto_generated": True
        }
    },
    {
        "file_name": "tests/unit/remediation/redshift-cluster.tf",
        "fix_suggestion": {
            "start_line": 1,
            "end_line": 1,
            "guidelines": "**Issue Type**: MissingAttribute\n**Expected value**: aws_redshift_cluster.encrypted is "
                          "defined and not null\n**Actual value**: aws_redshift_cluster.encrypted is undefined or null",
            "title": "Redshift Not Encrypted",
            "reason": "Encryption - AWS Redshift Cluster should be encrypted. Check if 'encrypted' field is false or"
                      " undefined (default is false). ",
            "filename": "tests/unit/remediation/redshift-cluster.tf",
            "current_text": "resource \"aws_redshift_cluster\" \"positive1\" {",
            "new_text": "resource \"aws_redshift_cluster\" \"positive1\" {\n  encrypted = true",
            "is_auto_generated": True
        }
    },
    {
        "file_name": "tests/unit/remediation/aws-s3-public-access.tf",
        "fix_suggestion": {
            "start_line": 20,
            "end_line": 20,
            "guidelines": "**Issue Type**: IncorrectValue\n**Expected value**: 'restrict_public_buckets' is equal "
                          "'true'\n**Actual value**: 'restrict_public_buckets' is equal 'false'",
            "title": "S3 Bucket Without Restriction Of Public Bucket",
            "reason": "Insecure Configurations - S3 bucket without restriction of public bucket. ",
            "filename": "tests/unit/remediation/aws-s3-public-access.tf",
            "current_text": "  restrict_public_buckets = false",
            "new_text": "  restrict_public_buckets = true",
            "is_auto_generated": True
        }
    },
    {
        "file_name": "tests/unit/remediation/aws-s3-public-access.tf",
        "fix_suggestion": {
            "start_line": 23,
            "end_line": 23,
            "guidelines": "**Issue Type**: MissingAttribute\n**Expected value**: 'restrict_public_buckets' is equal "
                          "'true'\n**Actual value**: 'restrict_public_buckets' is missing",
            "title": "S3 Bucket Without Restriction Of Public Bucket",
            "reason": "Insecure Configurations - S3 bucket without restriction of public bucket. ",
            "filename": "tests/unit/remediation/aws-s3-public-access.tf",
            "current_text": "resource \"aws_s3_bucket_public_access_block\" \"positive3\" {",
            "new_text": "resource \"aws_s3_bucket_public_access_block\" \"positive3\" {\n  "
                        "restrict_public_buckets = true",
            "is_auto_generated": True
        }
    },
]


def does_fix_exist_in_queries(fix: Dict, queries: Dict):
    for query in queries:
        for file in query['files']:
            if file.get('fix_suggestion'):
                does_file_exist = file['file_name'] == fix['file_name']
                does_fix_suggestion_exist = file['fix_suggestion'] == fix['fix_suggestion']
                if does_file_exist and does_fix_suggestion_exist:
                    return True
    return False


def test_auto_remediation():
    with open('./tests/unit/results_with_remediation.json', 'r') as f:
        kics_output = json.load(f)
    add_fix_suggestions_where_possible(kics_output)
    queries = kics_output['queries']
    for fix in required_fixes:
        assert does_fix_exist_in_queries(fix, queries)
