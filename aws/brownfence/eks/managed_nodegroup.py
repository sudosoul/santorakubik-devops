import pulumi
import pulumi_aws as aws
import pulumi_eks as eks


class ManagedNodeGroup:
    name: str
    kms_key: aws.kms.Key
    cluster: eks.Cluster
    subnet_ids: list[str]
    volume_size = 60
    desired_size = 1
    min_size = 1
    max_size = 2
    instance_type = "t3.small"
    

    def __init__(self, **kwargs) -> eks.ManagedNodeGroup:
        # Ensure required args set:
        if 'name' not in kwargs:
            raise "`name` not provided"
        if 'kms_key' not in kwargs:
            raise "`kms_key` not provided"
        else:
            if type(kwargs['kms_key']) != aws.kms.Key:
                raise "`kms_key` must be of type: `aws.kms.Key`"
        if 'cluster' not in kwargs:
            raise "`cluster` not provided"
        else:
            if type(kwargs['cluster']) != eks.Cluster:
                raise "`cluster` must be of type: `eks.Cluster`"

        # Override defaults
        for kwarg in kwargs:
            self.__setattr__(kwarg, kwargs[kwarg])

        
    def _build_launch_template(self) -> aws.ec2.LaunchTemplate:                                             
        launch_template = aws.ec2.LaunchTemplate(f"cluster-ng-{self.name}-launch-template",
            block_device_mappings=[
                aws.ec2.LaunchTemplateBlockDeviceMappingArgs(
                    device_name="/dev/xvda",
                    ebs=aws.ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                        delete_on_termination="false",
                        encrypted=True,
                        kms_key_id=self.kms_key.arn,
                        volume_size=self.volume_size
                    )
                )
            ],
            key_name="brownfence-cluster-ssh-keypair",
            instance_type=self.instance_type,
            update_default_version=True,
            tag_specifications=[aws.ec2.LaunchTemplateTagSpecificationArgs(
                resource_type="instance",
                tags={
                    "Name": f"brownfence-eks-node-{self.name}",
                    "nodegroup": f"brownfence-cluster-ng-{self.name}",
                    "cluster": "brownfence"
                },
            )]
        )

        return launch_template

    def create(self) -> eks.ManagedNodeGroup:
        launch_template = self._build_launch_template()
        managed_nodegroup = eks.ManagedNodeGroup(f"cluster-ng-{self.name}",
            cluster=self.cluster,
            cluster_name=self.cluster.eks_cluster.name,
            launch_template = {
                "id": launch_template.id,
                "version": launch_template.latest_version
            },
            node_group_name=f"browfence-cluster-ng-{self.name}",
            node_role_arn=self.cluster.core.instance_roles[0].arn,
            scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                desired_size=self.desired_size,
                min_size=self.min_size,
                max_size=self.max_size
            ),
            labels={
                "ng": self.name
            },
            subnet_ids=self.subnet_ids,
            opts=pulumi.ResourceOptions(parent=self.cluster)
        )


        
        return managed_nodegroup