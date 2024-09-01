import pytest

from src.lib.findings.identify_invalid_findings_upload import _calc_findings_text_distance
from tests.fixtures import build_finding_dict


def test_calc_findings_text_distance__exact_match():
    finding_dict = build_finding_dict()
    assert _calc_findings_text_distance(finding_dict, finding_dict) == 1.0


@pytest.mark.parametrize('key, first_value, second_value, expected_distance', [
    ('location_text', 'jitsecurity/findings-service', 'jitsecurity/github-service', 0.9862068965517241),
    ("test_id", 'B15', 'A955', 0.9941245593419507),
    ("test_name", 'cloudtrail with s3', 'cloudtrail logs do not exist', 0.9787735849056604),
    ("issue_text", 'Cloudtrail with S3 for archiving is not defined', 'Could not find cloudtrail logs',
     0.9377382465057179),
    ("issue_severity", 'HIGH', 'LOW', 0.9917936694021102),
    ("plan_layer", 'operations', 'runtime', 0.9872241579558653),
    ("vulnerability_type", 'secret', 'code_vulnerability', 0.9785714285714285),
    ("location", 'https://platform.staging.jit.io/my_secret_file.png',
     'https://platform.staging.jit.io/logo192.png',
     0.9747675962815405),
    ("code_attributes", {  # The diff here is in both line range and code_snippet
        "branch": "master",
        "pr_number": "2",
        "filename": "detect/detect_test.go",
        "line_range": "20-20",
        "code_snippet": "aws_redshift_cluster.encrypted is true",
        "head_sha": "6b431f33690352e7a64b9a3c0bed3e60aac28a42",
        "base_sha": "b6a13b81b41d259995dd8720d202e5297bdd19fd",
        "last_head_sha": "6b431f33690352e7a64b9a3c0bed3e60aac28a42",
        "user_vendor_id": "129313939",
        "user_vendor_username": "GeorgeCostanzaArchitecture"
    }, {
         "branch": "master",
         "pr_number": "2",
         "filename": "detect/detect_test.go",
         "line_range": "67-67",
         "code_snippet": "REDACTED",
         "head_sha": "6b431f33690352e7a64b9a3c0bed3e60aac28a42",
         "base_sha": "b6a13b81b41d259995dd8720d202e5297bdd19fd",
         "last_head_sha": "6b431f33690352e7a64b9a3c0bed3e60aac28a42",
         "user_vendor_id": "129313939",
         "user_vendor_username": "GeorgeCostanzaArchitecture"
     }, 0.9486692015209125),
    ("cloud_attributes", {
        "account_id": "123456789096",
        "account_name": "123456789096",
        "region": "us-west-1",
        "cloud_service_name": "s3"
    }, {
         "account_id": "963685750466",
         "account_name": "963685750466",
         "region": "us-east-1",
         "cloud_service_name": "iam"
     }, 0.9636552440290758),
])
def test_calc_findings_text_distance__same_finding_with_small_difference(key, first_value, second_value,
                                                                         expected_distance):
    """
    We assume that the applied differences won't affect the text distance significantly.
    """
    finding_dict_1 = build_finding_dict()
    finding_dict_2 = build_finding_dict()

    finding_dict_1[key] = first_value
    finding_dict_2[key] = second_value

    assert _calc_findings_text_distance(finding_dict_1, finding_dict_2) == expected_distance


def test_calc_findings_text_distance__different_findings_in_same_upload():
    """
    This is a real-life example of two different KICS findings that were uploaded to the same upload.
    We expect the text distance to be low (less than 0.9).
    """
    f1 = {
        'test_name': "Customer Master Keys (CMK) must have rotation enabled, which means the attribute"
                     " 'enable_key_rotation' must be set to 'true' when the key is enabled.",
        'issue_text': "Customer Master Keys (CMK) must have rotation enabled, which means the attribute"
                      " 'enable_key_rotation' must be set to 'true' when the key is enabled.",
        'issue_severity': 'HIGH', 'plan_layer': 'infrastructure',
        'vulnerability_type': 'cloud_infrastructure_misconfiguration',
        'location': 'https://github.com/foo/infra/blob/aa45dadfe848f803acab4c621fbdffa9f4c3939b/terraform-repo'
                    '/file_name_1.tf#L54-L54',
        'location_text': 'myOrg/infra',
        'code_attributes': {
            'branch': 'master',
            'pr_number': None,
            'filename': 'terraform-repo/infra.tf',
            'line_range': '54-54',
            'code_snippet': 'aws_kms_key[staging_dr_cloudwatch_key].enable_key_rotation is undefined',
            'head_sha': 'aa45dadfe848f803acab4c621fbdffa9f4c3939b', 'base_sha': '',
            'last_head_sha': 'aa45dadfe848f803acab4c621fbdffa9f4c3939b',
            'user_vendor_id': '96787573',
            'user_vendor_username': 'my_org-eyal'
        },
    }

    f2 = {
        'test_name': 'IAM Database Auth Enabled should be configured to true when using compatible engine and version',
        'issue_text': 'IAM Database Auth Enabled should be configured to true when using compatible engine and version',
        'issue_severity': 'HIGH',
        'plan_layer': 'infrastructure',
        'vulnerability_type': 'cloud_infrastructure_misconfiguration',
        'location': 'https://github.com/foo/infra/blob/aa45dadfe848f803acab4c621fbdffa9f4c3939b/terraform-fusion'
                    '/platform_rds.tf#L40-L40',
        'location_text': 'myOrg/infra',
        'code_attributes': {
            'branch': 'master',
            'pr_number': None,
            'filename': 'terraform-fusion/platform_rds.tf',
            'line_range': '40-40',
            'code_snippet': "'iam_database_authentication_enabled' is undefined or null",
            'head_sha': 'aa45dadfe848f803acab4c621fbdffa9f4c3939b', 'base_sha': '',
            'last_head_sha': 'aa45dadfe848f803acab4c621fbdffa9f4c3939b',
            'user_vendor_id': '96787573',
            'user_vendor_username': 'my_org-eyal'
        },
    }

    assert _calc_findings_text_distance(f1, f2) == 0.6795698924731183
