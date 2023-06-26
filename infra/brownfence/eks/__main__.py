import pulumi
import pulumi_eks as eks
import pulumi_aws as aws
import pulumi_tls as tls
import iam
import kms

config = pulumi.Config()
vpc_stack = pulumi.StackReference("santorakubik/brownfence/vpc")
vpn_stack = pulumi.StackReference("santorakubik/brownfence/vpn")

# Make sure we are deploying to Santorakubik:
if aws.get_caller_identity().account_id != "927123100668":
    print(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")
    exit()


# configure cluster sg
cluster_sg = aws.ec2.SecurityGroup("cluster-sg",
    name="brownfence-eks-cluster-sg",
    vpc_id=vpc_stack.get_output("vpc_id"),
    ingress=[
        # Allow all traffic from `this` SG
        aws.ec2.SecurityGroupIngressArgs(
            from_port=0,
            to_port=0,
            protocol="all",
            self=True,
            description="allow all traffic from this sg"
        ),
        # Allow all traffic from VPN
        aws.ec2.SecurityGroupIngressArgs(
            from_port=0,
            to_port=0,
            protocol="all",
            security_groups=[vpn_stack.get_output("vpn_sg_id")],
            description="allow all traffic from vpn"
        )
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            from_port=0,
            to_port=0,
            protocol="all",
            cidr_blocks=["0.0.0.0/0"],
            ipv6_cidr_blocks=["::/0"]
        )
    ],
    tags={
        "Name": "brownfence-eks-cluster-sg"
    }
)

# create cluster ssh key pair & save to SSM
ssh_keypair = tls.PrivateKey("ssh-keypair", algorithm="ED25519")
aws.ssm.Parameter("org_vpn_client_private_key", 
    type="SecureString", 
    name="/brownfence/eks/ssh_private_key", 
    value=pulumi.Output.secret(ssh_keypair.private_key_openssh)
)
aws.ssm.Parameter("org_vpn_client_public_key", 
    type="String", 
    name="/brownfence/eks/ssh_public_key", 
    value=ssh_keypair.public_key_openssh
)
ec2_keypair = aws.ec2.KeyPair("cluster-ssh-keypair", key_name="brownfence-cluster-ssh-keypair", public_key=ssh_keypair.public_key_openssh)

cluster_kms_key = kms.create_cluster_kms_key()


# Map AWS IAM users in `sfk-admins` group to Kubernetes internal RBAC admin group. 
#
# Mapping individual users avoids having to go from a group to a role with assume-role policies.
# Kubernetes has its own permissions (RBAC) system, with predefined groups for
# common permissions levels. AWS EKS provides translation from IAM to that, but we
# must explicitly map particular users or roles that should be granted permissions
# within the cluster.
#
# AWS docs: https://docs.aws.amazon.com/eks/latest/userguide/add-user-role.html
# Detailed example: https://apperati.io/articles/managing_eks_access-bs/
# IAM groups are not supported, only users or roles:
#     https://github.com/kubernetes-sigs/aws-iam-authenticator/issues/176
user_mappings = []
for admin in aws.iam.get_group(group_name="skf-admins").users:
    user_mappings.append(
        eks.UserMappingArgs(
            # AWS IAM user to set permissions for
            user_arn=admin.arn,
            # k8s RBAC group from which this IAM user will get permissions
            groups=["system:masters"],
            # k8s RBAC username to create for the user
            username=admin.arn.replace(f"arn:aws:iam::{aws.get_caller_identity().account_id}:user/", ""),
        )
    )

# configure cluster
cluster_instance_role = iam.create_role("cluster-ng-role")
cluster = eks.Cluster("cluster",
    name="browfence-eks-cluster",
    create_oidc_provider=True,
    cluster_security_group=cluster_sg,
    skip_default_node_group=True,
    instance_roles=[cluster_instance_role],
    enabled_cluster_log_types=["api", "audit", "authenticator", "controllerManager", "scheduler"],
    endpoint_public_access=False,
    endpoint_private_access=True,
    vpc_id=vpc_stack.get_output("vpc_id"),
    private_subnet_ids=vpc_stack.get_output("private_subnet_ids"),
    public_subnet_ids=vpc_stack.get_output("public_subnet_ids"),
    storage_classes={
        "gp2": {
            "type": "gp2",
            "default": True,
            "encrypted": True,
            "kms_key_id": cluster_kms_key.arn,
            "allow_volume_expansion": True
        }
    },
    encryption_config_key_arn=cluster_kms_key.arn,
    node_group_options=eks.ClusterNodeGroupOptionsArgs(
        encrypt_root_block_device=True,
        node_associate_public_ip_address=False,
        node_public_key=ssh_keypair.public_key_openssh,
        key_name="brownfence-cluster-ssh-keypair"
    ),
    user_mappings=user_mappings
)

# Update the default cluster SG to allow SSH from VPN
aws.ec2.SecurityGroupRule("cluster-default-sg-custom-rule-1",
    description="allow SSH from VPN",
    type="ingress",
    from_port=22,
    to_port=22,
    protocol="tcp",
    source_security_group_id=vpn_stack.get_output("vpn_sg_id"),
    security_group_id=cluster.core.cluster.vpc_config.cluster_security_group_id
)


cluster_nodegroup_launch_template = aws.ec2.LaunchTemplate("cluster-ng-launch-template",
    block_device_mappings=[
        aws.ec2.LaunchTemplateBlockDeviceMappingArgs(
            device_name="/dev/xvda",
            ebs=aws.ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                delete_on_termination="false",
                encrypted=True,
                kms_key_id=cluster_kms_key.arn,
                volume_size=120
            )
        )
    ],
    key_name="brownfence-cluster-ssh-keypair",
    update_default_version=True,
    tag_specifications=[aws.ec2.LaunchTemplateTagSpecificationArgs(
        resource_type="instance",
        tags={
            "Name": "brownfence-eks-node",
        },
    )]
)


# create cluster nodegroup
cluster_nodegroup = eks.ManagedNodeGroup("cluster-ng",
    cluster=cluster,
    cluster_name="browfence-eks-cluster",
    launch_template = {
        "id": cluster_nodegroup_launch_template.id,
        "version": cluster_nodegroup_launch_template.latest_version
    },
    node_group_name="browfence-cluster-ng",
    node_role_arn=cluster_instance_role.arn,
    scaling_config=aws.eks.NodeGroupScalingConfigArgs(
        desired_size=2,
        min_size=2,
        max_size=2
    ),
    instance_types=["t3.medium"],
    subnet_ids=vpc_stack.get_output("private_subnet_ids"),
    opts=pulumi.ResourceOptions(parent=cluster)
)




pulumi.export("kubeconfig", pulumi.Output.secret(cluster.kubeconfig))
