import pulumi
import pulumi_aws as aws

config = pulumi.Config()
vpc_stack = pulumi.StackReference("santorakubik/brownfence/vpc")
domain = config.require("domain")

# Make sure we are deploying to Santorakubik:
if pulumi.get_organization() != "santorakubik":
    raise Exception(f"ERROR: IN WRONG PULUMI ORG!\nCurrent ORG:{pulumi.get_organization()}")
if aws.get_caller_identity().account_id != "927123100668":
    raise Exception(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")


# configure alb sg
alb_sg = aws.ec2.SecurityGroup("alb-sg",
    name="brownfence-alb-sg",
    vpc_id=vpc_stack.get_output("vpc_id"),
    ingress=[
        # Allow HTTP/HTTPS
        aws.ec2.SecurityGroupIngressArgs(
            from_port=80,
            to_port=80,
            protocol="tcp",
            cidr_blocks=["0.0.0.0/0"],
            ipv6_cidr_blocks=["::/0"]
        ),
        aws.ec2.SecurityGroupIngressArgs(
            from_port=443,
            to_port=443,
            protocol="tcp",
            cidr_blocks=["0.0.0.0/0"],
            ipv6_cidr_blocks=["::/0"]
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
        "Name": "brownfence-alb-sg"
    }
)

alb = aws.lb.LoadBalancer("alb",
    name="brownfence-alb",
    security_groups=[alb_sg.id],
    subnets=vpc_stack.get_output("public_subnet_ids"),
    tags={
        "Name": "brownfence-alb",
    }
)


# Create ACM cert
certificate = aws.acm.Certificate("certificate",
    domain_name=f"*.{domain}",
    subject_alternative_names=[domain],
    validation_method="DNS",
)

# # Create route53 records to validate certificate ownership
# validation_record = aws.route53.Record(f"certificate-validation-record",
#     name=certificate.domain_validation_options[1].resource_record_name,
#     records=[certificate.domain_validation_options[1].resource_record_value],
#     ttl=60,
#     type=certificate.domain_validation_options[1].resource_record_type,
#     zone_id=aws.route53.get_zone(name="colerange.us").zone_id,
#     opts=pulumi.ResourceOptions(depends_on=[certificate])
# )


# # Validate the certificate 
# certificate_validation = aws.acm.CertificateValidation("certificate-validation",
#     certificate_arn=certificate.arn,
#     validation_record_fqdns=[validation_record.fqdn],
#     opts=pulumi.ResourceOptions(depends_on=[certificate,validation_record])
# )

# Create DNS entries
aws.route53.Record('r53-record-1',
    type='A', 
    name=domain,
    zone_id=aws.route53.get_zone(name="colerange.us").zone_id,
    aliases=[
      {
        'name': alb.dns_name,
        'zone_id': alb.zone_id,
        'evaluate_target_health': False
      }
    ],
    opts=pulumi.ResourceOptions(depends_on=[alb])
)
aws.route53.Record('r53-record-2',
    type='A', 
    name=f"zonk.{domain}",
    zone_id=aws.route53.get_zone(name="colerange.us").zone_id,
    aliases=[
      {
        'name': alb.dns_name,
        'zone_id': alb.zone_id,
        'evaluate_target_health': False
      }
    ],
    opts=pulumi.ResourceOptions(depends_on=[alb])
)



pulumi.export('alb-arn', alb.arn)
pulumi.export('acm-certificate-arn', certificate.arn)

