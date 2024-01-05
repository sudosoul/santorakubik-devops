import pulumi
import pulumi_aws as aws
import pulumi_aws_native as aws_native
import cluster
import services.nextcloud.__main__ as nextcloud_service

# Make sure we are deploying to Santorakubik:
if pulumi.get_organization() != "santorakubik-v2":
    raise Exception(f"ERROR: IN WRONG PULUMI ORG!\nCurrent ORG:{pulumi.get_organization()}")
if aws.get_caller_identity().account_id != "701567759855":
    raise Exception(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")


ecs_cluster = cluster.create()
nextcloud_service.create()
