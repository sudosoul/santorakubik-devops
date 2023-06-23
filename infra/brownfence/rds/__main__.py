#####################################################################################
# I disabled this for now mainly for cost reasons.
# But also, this requires 3AZs, and we are using a 2AZ vpc for cost savings.
#####################################################################################

# import pulumi
# import pulumi_aws as aws
# import pulumi_random as random

# config = pulumi.Config()
# vpc_stack = pulumi.StackReference("santorakubik/brownfence/vpc")

# # Make sure we are deploying to Santorakubik:
# if aws.get_caller_identity().account_id != "927123100668":
#     print(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")
#     exit()

# # Create DB subnet group
# db_subnet_group = aws.rds.SubnetGroup("db_subnet_group",
#     name="nextcloud-db-subnet-group",
#     subnet_ids=vpc_stack.get_output("private_subnet_ids"),
#     tags={
#         "Name": "nextcloud-db-subnet-group",
#     }
# )

# # Create DB KMS key
# db_kms_key = aws.kms.Key("db_kms_key",
#     deletion_window_in_days=30,
#     description="nextcloud-db-cluster-kms-key",
#     enable_key_rotation=True,
#     tags={
#         "Name": "nextcloud-db-cluster-kms-key"
#     }
# )

# # Create DB cluster
# db_master_username = "nextcloud"
# db_master_password = random.RandomPassword("db_master_password", length=32, special=True)
# db_cluster = aws.rds.Cluster("postgresql",
#     allocated_storage=250,
#     availability_zones=[
#         "us-east-2a",
#         "us-east-2b",
#         "us-east-2c"
#     ],
#     backup_retention_period=3,
#     cluster_identifier="nextcloud-db-cluster",
#     database_name="nextcloud",
#     db_cluster_instance_class="db.t3.small",
#     db_subnet_group_name="nextcloud-db-subnet-group",
#     deletion_protection=True,
#     enabled_cloudwatch_logs_exports=["audit", "error", "general", "slowquery", "postgresql"],
#     engine="postgres",
#     iops=1000,
#     kms_key_id=db_kms_key.arn,
#     master_username=db_master_username,
#     master_password=db_master_password.result,
#     preferred_backup_window="04:00-06:00",
#     storage_encrypted=True,
#     storage_type="gp3"
#     #opts=pulumi.ResourceOptions(ignore_changes=["availability_zones"])
# )

# # Save DB username and password to SSM
# aws.ssm.Parameter("ssm_ses_smtp_username", 
#     type="String", 
#     name="/nextcloud/db/username", 
#     value=db_master_username
# )
# aws.ssm.Parameter("ssm_ses_smtp_password", 
#     type="SecureString", 
#     name="/nextcloud/db/password", 
#     value=db_master_password.result
# )
