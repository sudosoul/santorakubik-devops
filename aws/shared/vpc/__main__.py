import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx

config = pulumi.Config()
vpc_name = config.require("vpc_name")
number_of_availability_zones = config.require_int("number_of_availability_zones")
vpc_cidr = config.require("vpc_cidr")

# Make sure we are deploying to Santorakubik:
if pulumi.get_organization() != "santorakubik":
    raise Exception(f"ERROR: IN WRONG PULUMI ORG!\nCurrent ORG:{pulumi.get_organization()}")
if aws.get_caller_identity().account_id != "927123100668":
    raise Exception(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")

# Create VPC with following specs:
# 2 public subnets / 2 private subnets
# 2 NAT Gateways each assigned a dedicated EIP
vpc = awsx.ec2.Vpc(vpc_name, 
  cidr_block = vpc_cidr,
  number_of_availability_zones = number_of_availability_zones,
  tags = {
      "Name": vpc_name,
      "managed_by": "pulumi"
  },
  opts=pulumi.ResourceOptions(ignore_changes=["tags"])
)

# Add k8s tags to subnets
vpc.public_subnet_ids.apply(lambda x: \
  [aws.ec2.Tag(\
      f"{i}-elb-tag", \
      resource_id=i, \
      key='kubernetes.io/role/elb', \
      value='1')\
  for i in x]\
)
vpc.private_subnet_ids.apply(lambda x: \
  [aws.ec2.Tag(\
      f"{i}-elb-tag", \
      resource_id=i, \
      key='kubernetes.io/role/internal-elb', \
      value='1')\
  for i in x]\
)

pulumi.export("vpc_id", vpc.vpc_id)
pulumi.export("outbound_ips", [vpc.eips[i].public_ip for i in range(number_of_availability_zones)])
pulumi.export("public_subnet_ids", vpc.public_subnet_ids)
pulumi.export("private_subnet_ids", vpc.private_subnet_ids)

