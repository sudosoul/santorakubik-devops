import pulumi_aws as aws
import json

def create_cluster_kms_key():
    cluster_kms_key = aws.kms.Key("cluster-kms-key",
        deletion_window_in_days=30,
        description="brownfence-cluster-kms-key",
        enable_key_rotation=True,
        policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Id": "key-default-1",
                "Statement": [
                    {
                        "Sid": "Enable IAM User Permissions",
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": f"arn:aws:iam::{aws.get_caller_identity().account_id}:root"
                        },
                        "Action": "kms:*",
                        "Resource": "*"
                    },
                    {
                        "Sid": "Allow service-linked role use of the customer managed key",
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": f"arn:aws:iam::{aws.get_caller_identity().account_id}:role/aws-service-role/autoscaling.amazonaws.com/AWSServiceRoleForAutoScaling"
                        },
                        "Action": [
                            "kms:Encrypt",
                            "kms:Decrypt",
                            "kms:ReEncrypt*",
                            "kms:GenerateDataKey*",
                            "kms:DescribeKey"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Sid": "Allow attachment of persistent resources",
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": f"arn:aws:iam::{aws.get_caller_identity().account_id}:role/aws-service-role/autoscaling.amazonaws.com/AWSServiceRoleForAutoScaling"
                        },
                        "Action": "kms:CreateGrant",
                        "Resource": "*",
                        "Condition": {
                            "Bool": {
                                "kms:GrantIsForAWSResource": "true"
                            }
                        }
                    }
                ]
            }
        ),
        tags={
            "Name": "brownfence-cluster-kms-key"
        }
    )

    return cluster_kms_key