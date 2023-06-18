import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx

config = pulumi.Config()
vpc_name = config.require("vpc_name")
number_of_availability_zones = config.require_int("number_of_availability_zones")
vpc_cidr = config.require("vpc_cidr")

# Make sure we are deploying to Santorakubik:
if aws.get_caller_identity().account_id != "927123100668":
    print(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")
    exit() 

# Create VPC with following specs:
# 2 public subnets / 2 private subnets
# 2 NAT Gateways each assigned a dedicated EIP
vpc = awsx.ec2.Vpc(vpc_name, 
  cidr_block = vpc_cidr,
  number_of_availability_zones = number_of_availability_zones,
  tags = {
      "Name": vpc_name,
      "managed_by": "pulumi"
  }
)

pulumi.export("vpc_id", vpc.id)
pulumi.export("outbound_ips", [vpc.eips[i].public_ip for i in range(number_of_availability_zones)])
pulumi.export("public_subnet_ids", vpc.public_subnet_ids)
pulumi.export("private_subnet_ids", vpc.private_subnet_ids)
