import pulumi
import pulumi_aws as aws
import pulumi_random as random

# Make sure we are deploying to Santorakubik:
if pulumi.get_organization() != "santorakubik-v2":
    raise Exception(f"ERROR: IN WRONG PULUMI ORG!\nCurrent ORG:{pulumi.get_organization()}")
if aws.get_caller_identity().account_id != "701567759855":
    raise Exception(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")

# # Create DB KMS key
db_kms_key = aws.kms.Key("brownfence-db-kms-key",
    deletion_window_in_days=30,
    description="brownfence-db-cluster-kms-key",
    enable_key_rotation=True,
    tags={
        "Name": "brownfence-db-cluster-kms-key"
    }
)

# Create DB cluster
db_master_username = "root"
db_master_password = random.RandomPassword("db_master_password", length=32, special=True)
brownfence_cluster = aws.rds.Cluster("brownfence-db-cluster",
    cluster_identifier="brownfence-db-cluster",
    engine="aurora-mysql",
    engine_mode="provisioned",
    engine_version="8.0.mysql_aurora.3.02.0",
    kms_key_id=db_kms_key.arn,
    master_username=db_master_username,
    master_password=db_master_password.result,
    serverlessv2_scaling_configuration=aws.rds.ClusterServerlessv2ScalingConfigurationArgs(
        max_capacity=1,
        min_capacity=0.5,
    ),
    storage_encrypted=True
)

brownfence_cluster_instance = aws.rds.ClusterInstance("brownfence-db-cluster-instance",
    cluster_identifier=brownfence_cluster.id,
    instance_class="db.serverless",
    engine=brownfence_cluster.engine,
    engine_version=brownfence_cluster.engine_version,
    publicly_accessible=True
)


# Save DB username and password to SSM
aws.ssm.Parameter("brownfence-ssm-db-username", 
    type="String", 
    name="/brownfence/db/username", 
    value=db_master_username
)
aws.ssm.Parameter("brownfence-ssm-db-password", 
    type="SecureString", 
    name="/brownfence/db/password", 
    value=db_master_password.result
)
