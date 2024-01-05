import pulumi
import pulumi_aws as aws
import pulumi_aws_native as aws_native
import pulumi_awsx as awsx

# Make sure we are deploying to Santorakubik:
if pulumi.get_organization() != "santorakubik-v2":
    raise Exception(f"ERROR: IN WRONG PULUMI ORG!\nCurrent ORG:{pulumi.get_organization()}")
if aws.get_caller_identity().account_id != "701567759855":
    raise Exception(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")


def create():
    nextcloud_nginx_repository = awsx.ecr.Repository("nextcloud-nginx-repository",
        awsx.ecr.RepositoryArgs(
            force_delete=True
        ),
        name="nextcloud-nginx"
    )

    nextcloud_nginx_image = awsx.ecr.Image("nextcloud-nginx-image",
        awsx.ecr.ImageArgs(
            repository_url=nextcloud_nginx_repository.url, 
            context="./services/nextcloud/files", 
            dockerfile="./services/nextcloud/files/Dockerfile.nginx", 
            platform="linux/amd64"
        ),
    )

