import pulumi
import pulumi_eks as eks
import pulumi_aws as aws
import iam

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
            description="allow all traffic from THIS sg"
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

# configure cluster
cluster_instance_role = iam.create_role("brownfence-eks-ng-role")
cluster = eks.Cluster("browfence-eks-cluster",
    name="browfence-eks-cluster",
    create_oidc_provider=True,
    cluster_security_group=cluster_sg,
    encrypt_root_block_device=True,
    skip_default_node_group=True,
    instance_roles=[cluster_instance_role],
    enabled_cluster_log_types=["api", "audit", "authenticator", "controllerManager", "scheduler"],
    endpoint_public_access=False,
    endpoint_private_access=True,
    vpc_id=vpc_stack.get_output("vpc_id"),
    private_subnet_ids=vpc_stack.get_output("private_subnet_ids"),
    public_subnet_ids=vpc_stack.get_output("public_subnet_ids"),
    storage_classes="gp2",
    node_associate_public_ip_address=False
)

# cluster_nodegroup = eks.ManagedNodeGroup(
#     "browfence-eks-ng",
#     cluster="browfence-eks-cluster",
#     cluster_name="browfence-eks-cluster",
#     node_group_name="browfence-eks-ng",
#     node_role_arn=cluster_instance_role.arn,
#     scaling_config=aws.eks.NodeGroupScalingConfigArgs(
#         desired_size=2,
#         min_size=2,
#         max_size=2
#     ),
#     instance_types=["t3.medium"],
#     disk_size=60,
#     subnet_ids=vpc_stack.get_output("private_subnet_ids")
# )

   