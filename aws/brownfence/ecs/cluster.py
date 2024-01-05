import pulumi
import pulumi_aws as aws
import pulumi_aws_native as aws_native


def create():
    # Create Cluster ASG / Capacity Provider
    cluster_launch_template = aws.ec2.LaunchTemplate("brownfence-cluster-launch-tmpl",
        name_prefix="brownfence",
        image_id="ami-01f446d4eeaed8a3c",
        instance_type="t2.medium"
    )
    cluster_asg = aws.autoscaling.Group("brownfence-ecs-cluster-asg",
        availability_zones=["us-east-1a", "us-east-1b", "us-east-1c"],
        launch_template=aws.autoscaling.GroupLaunchTemplateArgs(
            id=cluster_launch_template.id,
            version="$Latest",
        ),
        max_size=10,
        min_size=1,
        name="brownfence-ecs-cluster-asg",
        protect_from_scale_in=True,
        tags=[aws.autoscaling.GroupTagArgs(
            key="AmazonECSManaged",
            value="true",
            propagate_at_launch=True,
        )],
    )

    cluster_capacity_provider = aws.ecs.CapacityProvider("brownfence-ecs-cluster-capacity-provider", 
        auto_scaling_group_provider=aws.ecs.CapacityProviderAutoScalingGroupProviderArgs(
            auto_scaling_group_arn=cluster_asg.arn,
            managed_termination_protection="ENABLED",
            managed_scaling=aws.ecs.CapacityProviderAutoScalingGroupProviderManagedScalingArgs(
                maximum_scaling_step_size=1000,
                minimum_scaling_step_size=1,
                status="ENABLED",
                target_capacity=1,
            ),
        ),
        name="brownfence-ecs-cluster-capacity-provider"
    )
    ecs_cw_key = aws.kms.Key("brownfence-ecs-cw-key",
        description="brownfence-ecs-cw-key",
        deletion_window_in_days=30,
        enable_key_rotation=True
    )
    ecs_cw_log_group = aws.cloudwatch.LogGroup("brownfence-ecs-cluster-log-group")
    ecs_cluster = aws.ecs.Cluster("brownfence-ecs-cluster", 
        name="brownfence-ecs-cluster",
        configuration=aws.ecs.ClusterConfigurationArgs(
            execute_command_configuration=aws.ecs.ClusterConfigurationExecuteCommandConfigurationArgs(
                kms_key_id=ecs_cw_key.arn,
                logging="OVERRIDE",
                log_configuration=aws.ecs.ClusterConfigurationExecuteCommandConfigurationLogConfigurationArgs(
                    cloud_watch_encryption_enabled=True,
                    cloud_watch_log_group_name=ecs_cw_log_group.name,
                ),
        ),
    ))
    ecs_cluster_capacity_providers = aws.ecs.ClusterCapacityProviders("brownfence-ecs-cluster-capacity-providers",
        cluster_name=ecs_cluster.name,
        capacity_providers=[cluster_capacity_provider.name],
        default_capacity_provider_strategies=[aws.ecs.ClusterCapacityProvidersDefaultCapacityProviderStrategyArgs(
            base=1,
            weight=100,
            capacity_provider=cluster_capacity_provider.name
        )])
    
    return ecs_cluster
