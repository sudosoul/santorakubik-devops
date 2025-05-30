# import pulumi
# import pulumi_eks as eks
# import pulumi_aws as aws
# import pulumi_tls as tls
# import iam
# import kms
# import managed_nodegroup
# import json

# config = pulumi.Config()
# vpc_stack = pulumi.StackReference("santorakubik-v2/brownfence/vpc")
# #vpn_stack = pulumi.StackReference("santorakubik-v2/brownfence/vpn")

# # Make sure we are deploying to Santorakubik:
# if pulumi.get_organization() != "santorakubik-v2":
#     raise Exception(f"ERROR: IN WRONG PULUMI ORG!\nCurrent ORG:{pulumi.get_organization()}")
# if aws.get_caller_identity().account_id != "701567759855":
#     raise Exception(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")


# # configure cluster sg
# cluster_sg = aws.ec2.SecurityGroup("cluster-sg",
#     name="brownfence-eks-cluster-sg",
#     vpc_id=vpc_stack.get_output("vpc_id"),
#     ingress=[
#         # Allow all traffic from `this` SG
#         aws.ec2.SecurityGroupIngressArgs(
#             from_port=0,
#             to_port=0,
#             protocol="all",
#             self=True,
#             description="allow all traffic from this sg"
#         ),
#         # Allow all HTTPS traffic from anywhere
#         aws.ec2.SecurityGroupIngressArgs(
#             from_port=443,
#             to_port=443,
#             protocol="TCP",
#             cidr_blocks=["0.0.0.0/0"],
#             ipv6_cidr_blocks=["::/0"],
#             description="allow https traffic from anywhere"
#         )
#     ],
#     egress=[
#         aws.ec2.SecurityGroupEgressArgs(
#             from_port=0,
#             to_port=0,
#             protocol="all",
#             cidr_blocks=["0.0.0.0/0"],
#             ipv6_cidr_blocks=["::/0"]
#         )
#     ],
#     tags={
#         "Name": "brownfence-eks-cluster-sg"
#     }
# )

# # create cluster ssh key pair & save to SSM
# ssh_keypair = tls.PrivateKey("ssh-keypair", algorithm="ED25519")
# ec2_keypair = aws.ec2.KeyPair("cluster-ssh-keypair", key_name="brownfence-cluster-ssh-keypair", public_key=ssh_keypair.public_key_openssh)
# cluster_kms_key = kms.create_cluster_kms_key()


# # Map AWS IAM users in `sfk-admins` group to Kubernetes internal RBAC admin group. 
# #
# # AWS docs: https://docs.aws.amazon.com/eks/latest/userguide/add-user-role.html
# # Detailed example: https://apperati.io/articles/managing_eks_access-bs/
# # IAM groups are not supported, only users or roles:
# #     https://github.com/kubernetes-sigs/aws-iam-authenticator/issues/176
# # user_mappings = []
# # for admin in aws.iam.get_group(group_name="skf-admins").users:
# #     user_mappings.append(
# #         eks.UserMappingArgs(
# #             # AWS IAM user to set permissions for
# #             user_arn=admin.arn,
# #             # k8s RBAC group from which this IAM user will get permissions
# #             groups=["system:masters"],
# #             # k8s RBAC username to create for the user
# #             username=admin.arn.replace(f"arn:aws:iam::{aws.get_caller_identity().account_id}:user/", ""),
# #         )
# #     )

# # configure cluster
# cluster_instance_role = iam.create_cluster_role("cluster-ng-role")
# cluster_lb_role = iam.create_cluster_lb_controller_role()
# cluster = eks.Cluster("cluster",
#     name="browfence-eks-cluster",
#     create_oidc_provider=True,
#     cluster_security_group=cluster_sg,
#     skip_default_node_group=True,
#     instance_roles=[cluster_instance_role],
#     enabled_cluster_log_types=["api", "audit", "authenticator", "controllerManager", "scheduler"],
#     endpoint_public_access=True,
#     endpoint_private_access=False,
#     vpc_id=vpc_stack.get_output("vpc_id"),
#     #private_subnet_ids=vpc_stack.get_output("private_subnet_ids"),
#     public_subnet_ids=vpc_stack.get_output("public_subnet_ids"),
#     storage_classes={
#         "gp2": {
#             "type": "gp2",
#             "default": True,
#             "encrypted": True,
#             "kms_key_id": cluster_kms_key.arn,
#             "allow_volume_expansion": True
#         }
#     },
#     encryption_config_key_arn=cluster_kms_key.arn,
#     node_group_options=eks.ClusterNodeGroupOptionsArgs(
#         encrypt_root_block_device=True,
#         node_associate_public_ip_address=False,
#         node_public_key=ssh_keypair.public_key_openssh,
#         key_name="brownfence-cluster-ssh-keypair"
#     ),
#     #user_mappings=user_mappings
# )

# # Add k8s tags to subnets for aws lb discovery
# pulumi.Output.all(cluster_name=cluster.eks_cluster.name, subnet_ids=vpc_stack.get_output('public_subnet_ids')) \
#     .apply(lambda args: \
#         [aws.ec2.Tag(\
#             f"{subnet_id}-brownfence-cluster-tag", \
#             resource_id=subnet_id, \
#             key=f"kubernetes.io/cluster/{args['cluster_name']}", \
#             value='owned')\
#         for subnet_id in args['subnet_ids']]\
# )
# # pulumi.Output.all(cluster_name=cluster.eks_cluster.name, subnet_ids=vpc_stack.get_output('private_subnet_ids')) \
# #     .apply(lambda args: \
# #         [aws.ec2.Tag(\
# #             f"{subnet_id}-brownfence-cluster-tag", \
# #             resource_id=subnet_id, \
# #             key=f"kubernetes.io/cluster/{args['cluster_name']}", \
# #             value='shared')\
# #         for subnet_id in args['subnet_ids']]\
# # )

# # # Update the default cluster SG to allow SSH from VPN
# # aws.ec2.SecurityGroupRule("cluster-default-sg-custom-rule-1",
# #     description="allow SSH from VPN",
# #     type="ingress",
# #     from_port=22,
# #     to_port=22,
# #     protocol="tcp",
# #     source_security_group_id=vpc_stack.get_output("sg_id"),
# #     security_group_id=cluster.core.cluster.vpc_config.cluster_security_group_id
# # )

# # Create nodegroup according to Pulumi.eks.yaml config
# nodegroups = json.loads(config.get('nodegroups'))
# for nodegroup in nodegroups:
#     managed_nodegroup.ManagedNodeGroup(
#         name=nodegroup['name'],
#         kms_key=cluster_kms_key,
#         cluster=cluster,
#         subnet_ids=vpc_stack.get_output("public_subnet_ids"),
#         instance_type=nodegroup['instance_type'],
#         desired_size=nodegroup['desired_size'],
#         min_size=nodegroup['min_size'],
#         max_size=nodegroup['max_size'],
#     ).create()


# # Export to SSM & Pulumi
# aws.ssm.Parameter("cluster_ssh_private_key", 
#     type="SecureString", 
#     name="/brownfence/eks/ssh_private_key", 
#     value=pulumi.Output.secret(ssh_keypair.private_key_openssh),
#     overwrite=True
# )
# aws.ssm.Parameter("cluster_ssh_public_key", 
#     type="String", 
#     name="/brownfence/eks/ssh_public_key", 
#     value=ssh_keypair.public_key_openssh,
#     overwrite=True
# )
# pulumi.export("kubeconfig", pulumi.Output.secret(cluster.kubeconfig))
# pulumi.export('aws-lb-controller-role-arn', cluster_lb_role.arn)