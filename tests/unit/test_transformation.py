import json
from pathlib import Path

import yaml
from transformer import run_pipeline


def test_transformation():
    expected_findings = [
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 Buckets should not be readable and writable to all users",
            "test_name": "S3 Buckets should not be readable and writable to all users",
            "test_id": "d535387f",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "7-7",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without restriction of public bucket",
            "test_name": "S3 bucket without restriction of public bucket",
            "test_id": "a6e86c32",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                }
            ],
            "filename": "../../path/remediation/aws-s3-public-access.tf",
            "line_range": "20-20",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_name": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_id": "e1699d08",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "71-71",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without restriction of public bucket",
            "test_name": "S3 bucket without restriction of public bucket",
            "test_id": "a6e86c32",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                }
            ],
            "filename": "../../path/remediation/aws-s3-public-access.tf",
            "line_range": "23-23",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_name": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_id": "e1699d08",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                }
            ],
            "filename": "../../path/remediation/aws-s3-public-access.tf",
            "line_range": "1-1",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "AWS Redshift Clusters must not be publicly accessible. Check if 'publicly_accessible' field is true or undefined (default is true)",
            "test_name": "AWS Redshift Clusters must not be publicly accessible. Check if 'publicly_accessible' field is true or undefined (default is true)",
            "test_id": "9a581503",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/redshift_cluster",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/redshift_cluster",
                }
            ],
            "filename": "../../path/remediation/redshift-cluster.tf",
            "line_range": "10-10",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_name": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_id": "e1699d08",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "43-43",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_name": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_id": "b386c506",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "145-145",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_name": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_id": "b386c506",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                }
            ],
            "filename": "../../path/remediation/aws-s3-public-access.tf",
            "line_range": "1-1",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_name": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_id": "b386c506",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "43-43",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "AWS Redshift Cluster should be encrypted. Check if 'encrypted' field is false or undefined (default is false)",
            "test_name": "AWS Redshift Cluster should be encrypted. Check if 'encrypted' field is false or undefined (default is false)",
            "test_id": "2bee4895",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/redshift_cluster#encrypted",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/redshift_cluster#encrypted",
                }
            ],
            "filename": "../../path/remediation/redshift-cluster.tf",
            "line_range": "17-17",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_name": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_id": "e1699d08",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "118-118",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_name": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_id": "e1699d08",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "1-1",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_name": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_id": "b386c506",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "91-91",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 Bucket Object should have server-side encryption enabled",
            "test_name": "S3 Bucket Object should have server-side encryption enabled",
            "test_id": "e6b92744",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_object#server_side_encryption",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_object#server_side_encryption",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "24-24",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without restriction of public bucket",
            "test_name": "S3 bucket without restriction of public bucket",
            "test_id": "a6e86c32",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                }
            ],
            "filename": "../../path/remediation/aws-s3-public-access.tf",
            "line_range": "30-30",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without restriction of public bucket",
            "test_name": "S3 bucket without restriction of public bucket",
            "test_id": "a6e86c32",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "152-152",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "AWS Redshift Cluster should be encrypted. Check if 'encrypted' field is false or undefined (default is false)",
            "test_name": "AWS Redshift Cluster should be encrypted. Check if 'encrypted' field is false or undefined (default is false)",
            "test_id": "2bee4895",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/redshift_cluster#encrypted",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/redshift_cluster#encrypted",
                }
            ],
            "filename": "../../path/remediation/redshift-cluster.tf",
            "line_range": "1-1",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_name": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_id": "b386c506",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "66-66",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_name": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_id": "e1699d08",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "154-154",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket allows public policy",
            "test_name": "S3 bucket allows public policy",
            "test_id": "a8924b3b",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "145-145",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_name": "S3 bucket without MFA Delete Enabled. MFA delete cannot be enabled through Terraform, it can be done by adding a MFA device (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable.html) and enabling versioning and MFA delete by using AWS CLI: 'aws s3api put-bucket-versioning --versioning-configuration=Status=Enabled,MFADelete=Enabled --bucket=<BUCKET_NAME> --mfa=<MFA_SERIAL_NUMBER>'. Please, also notice that MFA delete can not be used with lifecycle configurations",
            "test_id": "e1699d08",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#mfa_delete",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "95-95",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "AWS Redshift Clusters must not be publicly accessible. Check if 'publicly_accessible' field is true or undefined (default is true)",
            "test_name": "AWS Redshift Clusters must not be publicly accessible. Check if 'publicly_accessible' field is true or undefined (default is true)",
            "test_id": "9a581503",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/redshift_cluster",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/redshift_cluster",
                }
            ],
            "filename": "../../path/remediation/redshift-cluster.tf",
            "line_range": "1-1",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "S3 bucket without restriction of public bucket",
            "test_name": "S3 bucket without restriction of public bucket",
            "test_id": "a6e86c32",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block",
                }
            ],
            "filename": "../../path/remediation/aws-s3-public-access.tf",
            "line_range": "6-6",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
        {
            "issue_severity": "HIGH",
            "issue_text": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_name": "If algorithm is AES256 then the master key is null, empty or undefined, otherwise the master key is required",
            "test_id": "b386c506",
            "references": [
                {
                    "name": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                    "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket#server_side_encryption_configuration",
                }
            ],
            "filename": "../../path/sample_file.tf",
            "line_range": "1-1",
            "fix_suggestion": None,
            "issue_confidence": "UNDEFINED",
        },
    ]
    with open(Path(__file__).parent.parent.parent / "pipeline.yml") as f:
        pipeline = yaml.safe_load(f)

    with open(
        Path(__file__).parent.parent.parent / "tests" / "unit" / "results.json"
    ) as f:
        output = json.loads(f.read())

    transformed = run_pipeline(pipeline, output)
    assert transformed.sort(key=lambda x: x["test_id"]) == expected_findings.sort(key=lambda x: x["test_id"])
