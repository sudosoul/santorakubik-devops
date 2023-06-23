import pulumi
import pulumi_eks as eks
import pulumi_aws as aws
import iam
import pulumi_tls as tls

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

# create cluster ssh key pair & save to SSM
cluster_ssh_keypair = tls.PrivateKey("brownfence-eks-ssh-keypair", algorithm="ED25519")
aws.ssm.Parameter("org_vpn_client_private_key", 
    type="SecureString", 
    name="/brownfence/eks/ssh_private_key", 
    value=cluster_ssh_keypair.private_key_openssh
)
aws.ssm.Parameter("org_vpn_client_public_key", 
    type="String", 
    name="/brownfence/eks/ssh_public_key", 
    value=cluster_ssh_keypair.public_key_openssh
)
ec2_keypair = aws.ec2.KeyPair("brownfence-ec2-ssh-keypair", key_name="brownfence-eks-ssh-keypair", public_key=cluster_ssh_keypair.public_key_openssh)

# create cluster storage kms key
cluster_kms_key = aws.kms.Key("brownfence-eks-cluster-kms-key",
    deletion_window_in_days=30,
    description="brownfence-eks-cluster-kms-key",
    enable_key_rotation=True,
    tags={
        "Name": "brownfence-eks-cluster-kms-key"
    }
)

# configure cluster
cluster_instance_role = iam.create_role("brownfence-eks-ng-role")
cluster = eks.Cluster("browfence-eks-cluster",
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
    storage_classes="gp2",
    node_associate_public_ip_address=False,
    node_public_key=cluster_ssh_keypair.public_key_openssh,
    encrypt_root_block_device=True,
    encryption_config_key_arn=cluster_kms_key.arn
    # node_group_options=eks.ClusterNodeGroupOptionsArgs(
    #     encrypt_root_block_device=True,
    #     node_associate_public_ip_address=False        
    # )
)


cluster_nodegroup = eks.ManagedNodeGroup(
    "browfence-eks-ng",
    cluster=cluster,
    cluster_name="browfence-eks-cluster",
    node_group_name="browfence-eks-ng",
    node_role_arn=cluster_instance_role.arn,
    scaling_config=aws.eks.NodeGroupScalingConfigArgs(
        desired_size=2,
        min_size=2,
        max_size=2
    ),
    instance_types=["t3.medium"],
    disk_size=120,
    subnet_ids=vpc_stack.get_output("private_subnet_ids"),
    remote_access=aws.eks.NodeGroupRemoteAccessArgs(
        ec2_ssh_key="brownfence-eks-ssh-keypair",
        source_security_group_ids=[cluster_sg.id]
    ),
    opts=pulumi.ResourceOptions(depends_on=[cluster, cluster_instance_role])
)

   