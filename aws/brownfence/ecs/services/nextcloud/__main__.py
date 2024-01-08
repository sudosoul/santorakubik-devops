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
    deploy_alb()
    
    def deploy_alb():
        alb_sg = create_alb_sg()
        alb = create_alb()
        default_tg = create_alb_default_targetgroup()
        alb_cert = create_alb_cert()
        create_alb_http_listener()
        create_alb_https_listener()
	
        def create_alb():
            alb = aws.alb.LoadBalancer('brownfence-nextcloud-alb',
                name="brownfence-nextcloud-alb",
                security_groups=[alb_sg.id],
                subnets=aws.ec2.get_subnets(filters=[aws.ec2.GetSubnetsFilterArgs(name="defaultForAz",values=["true"])]).ids,
                load_balancer_type="application",
            )

            return alb
        
        def create_alb_sg():
            alb_sg = aws.ec2.SecurityGroup("brownfence-nextcloud-alb-sg",
                description="Allow HTTP(S) inbound traffic",
                vpc_id=aws.ec2.get_vpc(default=True),
                ingress=[aws.ec2.SecurityGroupIngressArgs(
                    description="HTTP from internet",
                    from_port=80,
                    to_port=80,
                    protocol="tcp",
                    cidr_blocks=["0.0.0.0/0"],
                    ipv6_cidr_blocks=["::/0"],
                ), aws.ec2.SecurityGroupIngressArgs(
                    description="HTTPS from internet",
                    from_port=443,
                    to_port=443,
                    protocol="tcp",
                    cidr_blocks=["0.0.0.0/0"],
                    ipv6_cidr_blocks=["::/0"],
                )],
                egress=[aws.ec2.SecurityGroupEgressArgs(
                    from_port=0,
                    to_port=0,
                    protocol="-1",
                    cidr_blocks=["0.0.0.0/0"],
                    ipv6_cidr_blocks=["::/0"],
                )],
                tags={
                    "Name": "brownfence-nextcloud-alb-sg",
                })
            
            return alb_sg
	
        def create_alb_default_targetgroup():
            default_tg = aws.alb.TargetGroup("brownfence-nextcloud-alb-default-tg",
                deregistration_delay=60,
                health_check=aws.alb.TargetGroupHealthCheckArgs(
                    healthy_threshold=2,
                    interval=10,
                    matcher="200,400",
                    path="/status.php",
                    port="80",
                    timeout=5,
                    unhealthy_threshold=2
                ),
                port=80,
                protocol="HTTP",
                stickiness=aws.alb.TargetGroupStickinessArgs(type="lb_cookie", enabled=False),
                target_type="ip",
                vpc_id=aws.ec2.get_vpc(default=True),
                name="brownfence-nextcloud-alb-default-tg",
            )

            return default_tg       

        def create_alb_http_listener():
            http_listener = aws.alb.Listener("brownfence-nextcloud-alb-http-listener",
                load_balancer_arn=alb.arn,
                port=80,
                default_actions=[aws.alb.ListenerDefaultActionArgs(
                    type="redirect",
                    redirect=aws.alb.ListenerRedirectArgs(
                        protocol = "HTTPS",
                        port = 443,
                        host = "#{host}",
                        path = "/#{path}",
                        query = "#{query}",
                        statusCode = "HTTP_301"
                    )
                )],
            )

        def create_alb_cert():
            alb_cert = aws.acm.Certificate("brownfence-nextcloud-alb-cert",
                domain_name="vpn.colerange.vet",
                validation_method="DNS"
            )
            alb_cert_validation = aws.route53.Record("brownfence-nextcloud-alb-validation-record",
                name=alb_cert.domain_validation_options[0].resource_record_name,
                records=[alb_cert.domain_validation_options[0].resource_record_value],
                ttl=60,
                type=alb_cert.domain_validation_options[0].resource_record_type,
                zone_id=aws.route53.get_zone(name="colerange.vet", private_zone=False).zone_id
            )
            alb_cert_certificate_validation = aws.acm.CertificateValidation("brownfence-nextcloud-alb-validation",
                certificate_arn=alb_cert.arn,
                validation_record_fqdns=[alb_cert_validation.fqdn]
            )
            
            return alb_cert_certificate_validation
        
        def create_alb_https_listener():
            https_listener = aws.alb.Listener("brownfence-nextcloud-alb-https-listener",
                load_balancer_arn=alb.arn,
                port=443,
                protocol="HTTPS",
                ssl_policy="ELBSecurityPolicy-2016-08",  
                certificate_arn=alb_cert.certificate_arn,
                default_actions=[aws.alb.ListenerDefaultActionArgs(
                    type="forward",
                    target_group_arn=default_tg.arn,
                )]
            )

ecsService aws_native.ecs:Service" {
	options {
		dependsOn = [
			loadBalancerListener,
			efsMountTarget1,
			efsMountTarget2
		]
	}

	cluster = ecsCluster.id
	desiredCount = ecsInitialDesiredCapacity
	capacityProviderStrategy = [{
		base = 1,
		capacityProvider = ecsCapacityProvider,
		weight = 1
	}]
	deploymentConfiguration = {
		maximumPercent = 100,
		minimumHealthyPercent = 0
	}
	networkConfiguration = {
		awsvpcConfiguration = {
			assignPublicIp = "DISABLED",
			securityGroups = [ecsSecurityGroup.id],
			subnets = split(",", vpcStack.outputsPrivateSubnets)
		}
	}
	healthCheckGracePeriodSeconds = 2500
	loadBalancers = [{
		containerName = "nextcloud",
		containerPort = "80",
		targetGroupArn = loadBalancerTargetGroup.id
	}]
	schedulingStrategy = "REPLICA"
	taskDefinition = ecsTaskDefinition.id
	propagateTags = "SERVICE"
}

ecsTaskRole aws_native.iam:Role" {
	assumeRolePolicyDocument = {
		statement = [{
			effect = "Allow",
			principal = {
				service = ["ecs-tasks.amazonaws.com"]
			},
			action = ["sts:AssumeRole"]
		}]
	}
	path = "/"
	managedPolicyArns = [
		"arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
		"arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceAutoscaleRole"
	]
	policies = [{
		policyName = "ecs-service",
		policyDocument = {
			statement = [
				{
					effect = "Allow",
					action = [
						"elasticloadbalancing:DeregisterInstancesFromLoadBalancer",
						"elasticloadbalancing:DeregisterTargets",
						"elasticloadbalancing:Describe*",
						"elasticloadbalancing:RegisterInstancesWithLoadBalancer",
						"elasticloadbalancing:RegisterTargets"
					],
					= "*"
				},
				{
					effect = "Allow",
					action = [
						"ec2:Describe*",
						"ec2:AuthorizeSecurityGroupIngress",
						"ec2:AttachNetworkInterface",
						"ec2:CreateNetworkInterface",
						"ec2:CreateNetworkInterfacePermission",
						"ec2:DeleteNetworkInterface",
						"ec2:DeleteNetworkInterfacePermission",
						"ec2:Describe*",
						"ec2:DetachNetworkInterface"
					],
					= "*"
				},
				{
					effect = "Allow",
					action = ["elasticfilesystem:*"],
					= [
						"arn:aws:elasticfilesystem:${awsRegion}:${awsAccountId}:file-system/${efs.id}",
						"arn:aws:elasticfilesystem:${awsRegion}:${awsAccountId}:access-point/${efsAPNextcloud.id}",
						"arn:aws:elasticfilesystem:${awsRegion}:${awsAccountId}:access-point/${efsAPConfig.id}",
						"arn:aws:elasticfilesystem:${awsRegion}:${awsAccountId}:access-point/${efsAPApps.id}",
						"arn:aws:elasticfilesystem:${awsRegion}:${awsAccountId}:access-point/${efsAPData.id}"
					]
				}
			]
		}
	}]
}

ecsTaskExecRole aws_native.iam:Role" {
	assumeRolePolicyDocument = {
		statement = [{
			effect = "Allow",
			principal = {
				service = ["ecs-tasks.amazonaws.com"]
			},
			action = ["sts:AssumeRole"]
		}]
	}
	path = "/"
	managedPolicyArns = [
		"arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
		"arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
	]
	policies = [{
		policyName = "ecs-service",
		policyDocument = {
			statement = [
				{
					effect = "Allow",
					action = ["elasticfilesystem:*"],
					= [
						"arn:aws:elasticfilesystem:${awsRegion}:${awsAccountId}:file-system/${efs.id}",
						"arn:aws:elasticfilesystem:${awsRegion}:${awsAccountId}:access-point/${efsAPNextcloud.id}",
						"arn:aws:elasticfilesystem:${awsRegion}:${awsAccountId}:access-point/${efsAPConfig.id}",
						"arn:aws:elasticfilesystem:${awsRegion}:${awsAccountId}:access-point/${efsAPApps.id}",
						"arn:aws:elasticfilesystem:${awsRegion}:${awsAccountId}:access-point/${efsAPData.id}"
					]
				},
				{
					effect = "Allow",
					action = [
						"ecr:GetAuthorizationToken",
						"ecr:BatchCheckLayerAvailability",
						"ecr:GetDownloadUrlForLayer",
						"ecr:BatchGetImage"
					],
					= "*"
				},
				{
					effect = "Allow",
					action = ["s3:*"],
					= "arn:aws:s3:::${dataBucket.id}"
				},
				{
					effect = "Allow",
					action = ["s3:*"],
					= "arn:aws:s3:::${dataBucket.id}/*"
				},
				{
					effect = "Deny",
					action = [
						"s3:DeleteBucket*",
						"s3:PutBucket*",
						"s3:PutEncryptionConfiguration",
						"s3:CreateBucket"
					],
					= "*"
				},
				{
					effect = "Allow",
					action = ["s3:GetBucketLocation"],
					= "arn:aws:s3:::*"
				}
			]
		}
	}]
}

ec2NcRole aws_native.iam:Role" {
	assumeRolePolicyDocument = {
		statement = [{
			effect = "Allow",
			principal = {
				service = ["ec2.amazonaws.com"]
			},
			action = ["sts:AssumeRole"]
		}]
	}
	path = "/"
	managedPolicyArns = ["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"]
	policies = [{
		policyName = "ecs-service",
		policyDocument = {
			statement = [{
				effect = "Allow",
				action = [
					"logs:*",
					"elasticfilesystem:*"
				],
				= "*"
			}]
		}
	}]
}

instanceProfile aws_native.iam:InstanceProfile" {
	path = "/"
	roles = [ec2NcRole.id]
}

nextcloudAutoScalingRole aws_native.iam:Role" {
	assumeRolePolicyDocument = {
		statement = [{
			effect = "Allow",
			principal = {
				service = "ecs-tasks.amazonaws.com"
			},
			action = "sts:AssumeRole"
		}]
	}
	managedPolicyArns = ["arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceAutoscaleRole"]
}

nextcloudAutoScalingTarget aws_native.applicationautoscaling:ScalableTarget" {
	minCapacity = ecsMinCapacity
	maxCapacity = ecsMaxCapacity
	resourceId = "service/${ecsCluster.id}/${ecsService.name}"
	scalableDimension = "ecs:service:DesiredCount"
	serviceNamespace = "ecs"
	roleARN = nextcloudAutoScalingRole.arn
	suspendedState = {
		dynamicScalingInSuspended = suspendAutoScaling,
		dynamicScalingOutSuspended = suspendAutoScaling,
		scheduledScalingSuspended = suspendAutoScaling
	}
}

nextcloudAutoScalingPolicy aws_native.applicationautoscaling:ScalingPolicy" {
	policyName = ecsService.name
	policyType = "TargetTrackingScaling"
	scalingTargetId = nextcloudAutoScalingTarget.id
	targetTrackingScalingPolicyConfiguration = {
		predefinedMetricSpecification = {
			predefinedMetricType = "ECSServiceAverageCPUUtilization"
		},
		scaleInCooldown = 10,
		scaleOutCooldown = 10,
		targetValue = ecsTargetCpuUtilization
	}
}

