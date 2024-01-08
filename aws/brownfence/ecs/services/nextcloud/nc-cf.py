import pulumi
import pulumi_aws_native as aws

config deploymentName string {
	default = "nc-serverless"
}

config route53Zone string {
	default = ""
}

config domain string {
	default = ""
}

config dbUserName string {
	default = "nextcloud"
}

config dbPassword string {
}

config dbMinCapacity number {
	default = 2
}

config dbMaxCapacity number {
	default = 8
}

config nextCloudAdminUser string {
	default = "ncadmin"
}

config nextCloudAdminPassword string {
}

config nextCloudDbName string {
	default = "nextcloud"
}

config nextCloudVersion string {
	default = "23.0.1"
}

config s3SecretRotationSerial number {
	default = 1
}

config isolationLevel string {
	default = "Private"
}

config ecsCapacityProvider string {
	default = "FARGATE"
}

config ecsTaskCpu number {
	default = 1024
}

config ecsTaskMem number {
	default = 2048
}

config ecsMinCapacity number {
	default = 1
}

config ecsInitialDesiredCapacity number {
	default = 1
}

config ecsMaxCapacity number {
	default = 25
}

config ecsTargetCpuUtilization number {
	default = 50
}

config suspendAutoScaling string {
	default = false
}

config = {
	container = {
		uid = 33,
		gid = 0,
		permission = "0777"
	}
}
customDomain = !(domain == "" && route53Zone == "")
privateSubnets = !(isolationLevel == "Public")
resource vpcStack "aws-native:cloudformation:Stack" {
	templateURL = "./simplevpc.yaml"
	timeoutInMinutes = 60
	parameters = {
		environmentName = deploymentName,
		isolationLevel = isolationLevel
	}
}


resource ecsCluster "aws-native:ecs:Cluster" {
	capacityProviders = [
		"FARGATE",
		"FARGATE_SPOT"
	]
	configuration = {
		executeCommandConfiguration = {
			logging = "DEFAULT"
		}
	}
}

resource ecsSecurityGroup "aws-native:ec2:SecurityGroup" {
	groupDescription = "ECS Security Group"
	vpcId = vpcStack.outputsVpc
}

resource ecsSecurityGroupHTTPinbound "aws-native:ec2:SecurityGroupIngress" {
	groupId = ecsSecurityGroup.id
	ipProtocol = "tcp"
	fromPort = "80"
	toPort = "80"
	sourceSecurityGroupId = elbSecurityGroup.id
}

resource cloudwatchLogsGroup "aws-native:logs:LogGroup" {
	logGroupName = "-${"${deploymentName}"}-${awsStackName}"
	retentionInDays = 14
}

resource dataBucket "aws-native:s3:Bucket" {
	versioningConfiguration = {
		status = "Enabled"
	}
	bucketEncryption = {
		serverSideEncryptionConfiguration = [{
			bucketKeyEnabled = true,
			serverSideEncryptionByDefault = {
				sseAlgorithm = "AES256"
			}
		}]
	}
}

resource bucketUser "aws-native:iam:User" {
	policies = [{
		policyName = "s3-access",
		policyDocument = {
			statement = [
				{
					effect = "Allow",
					action = ["s3:*"],
					resource = "arn:aws:s3:::${dataBucket.id}"
				},
				{
					effect = "Allow",
					action = ["s3:*"],
					resource = "arn:aws:s3:::${dataBucket.id}/*"
				},
				{
					effect = "Deny",
					action = [
						"s3:DeleteBucket*",
						"s3:PutBucketPolicy",
						"s3:PutEncryptionConfiguration"
					],
					resource = "*"
				},
				{
					effect = "Allow",
					action = ["s3:GetBucketLocation"],
					resource = "arn:aws:s3:::*"
				}
			]
		}
	}]
}

resource bucketUserCredentials "aws-native:iam:AccessKey" {
	serial = s3SecretRotationSerial
	status = "Active"
	userName = bucketUser.id
}

resource efs "aws-native:efs:FileSystem" {
	encrypted = true
}

resource efsMountTarget1 "aws-native:efs:MountTarget" {
	fileSystemId = efs.id
	subnetId = split(",", vpcStack.outputsPrivateSubnets)[0]
	securityGroups = [efsSecurityGroup.id]
}

resource efsMountTarget2 "aws-native:efs:MountTarget" {
	fileSystemId = efs.id
	subnetId = split(",", vpcStack.outputsPrivateSubnets)[1]
	securityGroups = [efsSecurityGroup.id]
}

resource efsAPNextcloud "aws-native:efs:AccessPoint" {
	fileSystemId = efs.id
	rootDirectory = {
		path = "/${deploymentName}/nextcloud",
		creationInfo = {
			ownerUid = config["Container"]["Uid"],
			ownerGid = config["Container"]["Gid"],
			permissions = config["Container"]["Permission"]
		}
	}
}

resource efsAPConfig "aws-native:efs:AccessPoint" {
	fileSystemId = efs.id
	rootDirectory = {
		path = "/${deploymentName}/config",
		creationInfo = {
			ownerUid = config["Container"]["Uid"],
			ownerGid = config["Container"]["Gid"],
			permissions = config["Container"]["Permission"]
		}
	}
}

resource efsAPApps "aws-native:efs:AccessPoint" {
	fileSystemId = efs.id
	rootDirectory = {
		path = "/${deploymentName}/apps",
		creationInfo = {
			ownerUid = config["Container"]["Uid"],
			ownerGid = config["Container"]["Gid"],
			permissions = config["Container"]["Permission"]
		}
	}
}

resource efsAPData "aws-native:efs:AccessPoint" {
	fileSystemId = efs.id
	rootDirectory = {
		path = "/${deploymentName}/data",
		creationInfo = {
			ownerUid = config["Container"]["Uid"],
			ownerGid = config["Container"]["Gid"],
			permissions = config["Container"]["Permission"]
		}
	}
}

resource efsSecurityGroup "aws-native:ec2:SecurityGroup" {
	groupDescription = "ECS Security Group"
	vpcId = vpcStack.outputsVpc
}

resource efsSecurityGroupNFSinbound "aws-native:ec2:SecurityGroupIngress" {
	groupId = efsSecurityGroup.id
	ipProtocol = "tcp"
	fromPort = "2049"
	toPort = "2049"
	sourceSecurityGroupId = ecsSecurityGroup.id
}

resource ecsTaskDefinition "aws-native:ecs:TaskDefinition" {
	family = "${awsStackName}-ecs-nextcloud"
	networkMode = "awsvpc"
	requiresCompatibilities = ["FARGATE"]
	executionRoleArn = ecsTaskExecRole.arn
	taskRoleArn = ecsTaskRole.arn
	cpu = ecsTaskCpu
	memory = ecsTaskMem
	containerDefinitions = [{
		name = "nextcloud",
		logConfiguration = {
			logDriver = "awslogs",
			options = {
				awslogs-group = cloudwatchLogsGroup.id,
				awslogs-region = awsRegion,
				awslogs-stream-prefix = "nextcloud"
			}
		},
		environment = [
			{
				name = "POSTGRES_DB",
				value = nextCloudDbName
			},
			{
				name = "POSTGRES_USER",
				value = dbUserName
			},
			{
				name = "POSTGRES_PASSWORD",
				value = dbPassword
			},
			{
				name = "POSTGRES_HOST",
				value = rdsStack.outputsEndpointUrl
			},
			{
				name = "NEXTCLOUD_TRUSTED_DOMAINS",
				value = "${domain} ${elasticLoadBalancer.dnsName}"
			},
			{
				name = "NEXTCLOUD_ADMIN_USER",
				value = nextCloudAdminUser
			},
			{
				name = "NEXTCLOUD_ADMIN_PASSWORD",
				value = nextCloudAdminPassword
			},
			{
				name = "OBJECTSTORE_S3_BUCKET",
				value = dataBucket.id
			},
			{
				name = "OBJECTSTORE_S3_REGION",
				value = awsRegion
			},
			{
				name = "OBJECTSTORE_S3_KEY",
				value = bucketUserCredentials.id
			},
			{
				name = "OBJECTSTORE_S3_SECRET",
				value = bucketUserCredentials.secretAccessKey
			},
			{
				name = "OVERWRITEPROTOCOL",
				value = "https"
			}
		],
		portMappings = [{
			hostPort = 80,
			protocol = "tcp",
			containerPort = 80
		}],
		mountPoints = [
			{
				containerPath = "/var/www/html",
				sourceVolume = "nextcloud"
			},
			{
				containerPath = "/var/www/html/custom_apps",
				sourceVolume = "apps"
			},
			{
				containerPath = "/var/www/html/config",
				sourceVolume = "config"
			},
			{
				containerPath = "/var/www/html/data",
				sourceVolume = "data"
			}
		],
		image = "nextcloud:${nextCloudVersion}-apache",
		essential = true
	}]
	volumes = [
		{
			name = "nextcloud",
			efsVolumeConfiguration = {
				filesystemId = efs.id,
				authorizationConfig = {
					accessPointId = efsAPNextcloud.id,
					iam = "ENABLED"
				},
				transitEncryption = "ENABLED"
			}
		},
		{
			name = "apps",
			efsVolumeConfiguration = {
				filesystemId = efs.id,
				authorizationConfig = {
					accessPointId = efsAPApps.id,
					iam = "ENABLED"
				},
				transitEncryption = "ENABLED"
			}
		},
		{
			name = "config",
			efsVolumeConfiguration = {
				filesystemId = efs.id,
				authorizationConfig = {
					accessPointId = efsAPConfig.id,
					iam = "ENABLED"
				},
				transitEncryption = "ENABLED"
			}
		},
		{
			name = "data",
			efsVolumeConfiguration = {
				filesystemId = efs.id,
				authorizationConfig = {
					accessPointId = efsAPData.id,
					iam = "ENABLED"
				},
				transitEncryption = "ENABLED"
			}
		}
	]
}

resource albCertificate "aws-native:certificatemanager:Certificate" {
	domainName = domain
	validationMethod = "DNS"
	domainValidationOptions = [{
		domainName = domain,
		hostedZoneId = route53Zone
	}]
}

resource elbSecurityGroup "aws-native:ec2:SecurityGroup" {
	groupDescription = "ELB Security Group"
	vpcId = vpcStack.outputsVpc
}

resource elbSecurityGroupHTTPSinbound "aws-native:ec2:SecurityGroupIngress" {
	groupId = elbSecurityGroup.id
	ipProtocol = "tcp"
	fromPort = "443"
	toPort = "443"
	cidrIp = "0.0.0.0/0"
}

resource elbSecurityGroupHTTPinbound "aws-native:ec2:SecurityGroupIngress" {
	groupId = elbSecurityGroup.id
	ipProtocol = "tcp"
	fromPort = "80"
	toPort = "80"
	cidrIp = "0.0.0.0/0"
}

resource elasticLoadBalancer "aws-native:elasticloadbalancingv2:LoadBalancer" {
	scheme = "internet-facing"
	loadBalancerAttributes = [{
		key = "idle_timeout.timeout_seconds",
		value = "30"
	}]
	securityGroups = [elbSecurityGroup.id]
}

resource route53AliasRecord "aws-native:route53:RecordSet" {
	aliasTarget = {
		dnsName = elasticLoadBalancer.dnsName,
		evaluateTargetHealth = true,
		hostedZoneId = elasticLoadBalancer.canonicalHostedZoneId
	}
	comment = "Sso Api Gateway"
	hostedZoneId = route53Zone
	name = domain
	type = "A"
}

resource loadBalancerListener "aws-native:elasticloadbalancingv2:Listener" {
	defaultActions = [
		{
			type = "redirect",
			redirectConfig = {
				protocol = "HTTPS",
				port = 443,
				host = "#{host}",
				path = "/#{path}",
				query = "#{query}",
				statusCode = "HTTP_301"
			}
		},
		{
			type = "forward",
			targetGroupArn = loadBalancerTargetGroup.id
		}
	]
	loadBalancerArn = elasticLoadBalancer.id
	port = "80"
	protocol = "HTTP"
}

resource httpsLoadBalancerListener "aws-native:elasticloadbalancingv2:Listener" {
	certificates = [{
		certificateArn = albCertificate.id
	}]
	defaultActions = [{
		type = "forward",
		targetGroupArn = loadBalancerTargetGroup.id
	}]
	loadBalancerArn = elasticLoadBalancer.id
	port = "443"
	protocol = "HTTPS"
}

resource loadBalancerListenerRule "aws-native:elasticloadbalancingv2:ListenerRule" {
	options {
		dependsOn = [loadBalancerListener]
	}

	actions = [{
		type = "forward",
		targetGroupArn = loadBalancerTargetGroup.id
	}]
	conditions = [{
		field = "path-pattern",
		values = ["/"]
	}]
	listenerArn = loadBalancerListener.id
	priority = 1
}

resource loadBalancerTargetGroup "aws-native:elasticloadbalancingv2:TargetGroup" {
	options {
		dependsOn = [elasticLoadBalancer]
	}

	healthCheckIntervalSeconds = 10
	healthCheckPath = "/status.php"
	healthCheckProtocol = "HTTP"
	healthCheckTimeoutSeconds = 5
	healthyThresholdCount = 2
	port = 80
	protocol = "HTTP"
	matcher = {
		httpCode = "200,400"
	}
	unhealthyThresholdCount = 2
	vpcId = vpcStack.outputsVpc
	targetType = "ip"
	targetGroupAttributes = [
		{
			key = "deregistration_delay.timeout_seconds",
			value = 60
		},
		{
			key = "stickiness.enabled",
			value = false
		}
	]
}

resource ecsService "aws-native:ecs:Service" {
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

resource ecsTaskRole "aws-native:iam:Role" {
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
					resource = "*"
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
					resource = "*"
				},
				{
					effect = "Allow",
					action = ["elasticfilesystem:*"],
					resource = [
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

resource ecsTaskExecRole "aws-native:iam:Role" {
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
					resource = [
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
					resource = "*"
				},
				{
					effect = "Allow",
					action = ["s3:*"],
					resource = "arn:aws:s3:::${dataBucket.id}"
				},
				{
					effect = "Allow",
					action = ["s3:*"],
					resource = "arn:aws:s3:::${dataBucket.id}/*"
				},
				{
					effect = "Deny",
					action = [
						"s3:DeleteBucket*",
						"s3:PutBucket*",
						"s3:PutEncryptionConfiguration",
						"s3:CreateBucket"
					],
					resource = "*"
				},
				{
					effect = "Allow",
					action = ["s3:GetBucketLocation"],
					resource = "arn:aws:s3:::*"
				}
			]
		}
	}]
}

resource ec2NcRole "aws-native:iam:Role" {
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
				resource = "*"
			}]
		}
	}]
}

resource instanceProfile "aws-native:iam:InstanceProfile" {
	path = "/"
	roles = [ec2NcRole.id]
}

resource nextcloudAutoScalingRole "aws-native:iam:Role" {
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

resource nextcloudAutoScalingTarget "aws-native:applicationautoscaling:ScalableTarget" {
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

resource nextcloudAutoScalingPolicy "aws-native:applicationautoscaling:ScalingPolicy" {
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

output loadBalancerUrl {
	value = elasticLoadBalancer.dnsName
}

output customUrl {
	value = "https://${domain}"
}
