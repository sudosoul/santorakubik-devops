import pulumi
import pulumi_aws as aws
import os

resource_prefix = "org-vpn"
vpc_stack = pulumi.StackReference("santorakubik/brownfence/vpc")

# Make sure we are deploying to Santorakubik:
if aws.get_caller_identity().account_id != "927123100668":
    print(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")
    exit()


def create_vpn():
    ############ reqs ############
    def create_vpn_cw_loggroup():
        cw_loggroup = aws.cloudwatch.LogGroup(resource_prefix, name=resource_prefix, retention_in_days=365)
        return cw_loggroup
    
    def create_vpn_cw_logstream():
        cw_logstream = aws.cloudwatch.LogStream(
            resource_prefix, 
            name=resource_prefix, 
            log_group_name=resource_prefix,
            opts=pulumi.ResourceOptions(depends_on=[vpn_cw_loggroup])
        )
        return cw_logstream
    
    def create_vpn_server_cert():
        server_cert = aws.acm.Certificate("server-cert",
            domain_name="vpn.colerange.us",
            validation_method="DNS"
        )
        server_cert_validation = aws.route53.Record("server-cert-validation",
            name=server_cert.domain_validation_options[0].resource_record_name,
            records=[server_cert.domain_validation_options[0].resource_record_value],
            ttl=60,
            type=server_cert.domain_validation_options[0].resource_record_type,
            zone_id=aws.route53.get_zone(name="colerange.us", private_zone=False).zone_id
        )
        server_cert_certificate_validation = aws.acm.CertificateValidation("cert",
            certificate_arn=server_cert.arn,
            validation_record_fqdns=[server_cert_validation.fqdn]
        )
        
        return server_cert_certificate_validation

    def create_vpn_client_cert():
        # If this is a first time run, or if we are re-creating the client cert,
        # THEN get the private key from file path, and then delete it.
        # Else get it from SSM if file not exist (Existing Private Key).
        if os.path.isfile("certs/client.vpn.colerange.us.key"):
            with open("certs/client.vpn.colerange.us.key") as fp:
                private_key = fp.read()
                fp.close()
            os.remove("certs/client.vpn.colerange.us.key")
        else:
            private_key = aws.ssm.get_parameter(name="/org/vpn/client_private_key").value
        # have these throw exceptiont to OS if files not found
        with open("certs/client.vpn.colerange.us.crt") as fp:
            certificate_body = fp.read()
        with open("certs/ca.crt") as fp:
            certificate_chain = fp.read()
        
        client_cert = aws.acm.Certificate("client-cert",
            private_key=private_key,
            certificate_body=certificate_body,
            certificate_chain=certificate_chain
        )
        aws.ssm.Parameter("org_vpn_client_private_key", 
            type="SecureString", 
            name="/org/vpn/client_private_key", 
            value=private_key
        )
        aws.ssm.Parameter("org_vpn_client_public_key", 
            type="String", 
            name="/org/vpn/client_public_key", 
            value=certificate_body
        )
        
        return client_cert
    
    def create_vpn_sg():
        vpn_sg = aws.ec2.SecurityGroup(f"{resource_prefix}-sg",
            description=f"{resource_prefix}-sg",
            vpc_id=vpc_stack.get_output("vpc_id"),
            ingress=[aws.ec2.SecurityGroupIngressArgs(
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
                "Name": f"{resource_prefix}-sg",
            })
        pulumi.export("vpn_sg_id", vpn_sg.id)
        return vpn_sg
    
    ############ vpn ############
    vpn_cw_loggroup   = create_vpn_cw_loggroup()
    vpn_cw_logstream  = create_vpn_cw_logstream()
    vpn_server_cert   = create_vpn_server_cert()
    vpn_client_cert   = create_vpn_client_cert()
    vpn_sg            = create_vpn_sg()


    vpn = aws.ec2clientvpn.Endpoint(resource_prefix,
        description=resource_prefix,
        client_cidr_block="192.168.0.0/22",
        authentication_options=[aws.ec2clientvpn.EndpointAuthenticationOptionArgs(
            type="certificate-authentication",
            root_certificate_chain_arn=vpn_client_cert.arn
        )],
        connection_log_options=aws.ec2clientvpn.EndpointConnectionLogOptionsArgs(
            enabled=True,
            cloudwatch_log_group=resource_prefix,
            cloudwatch_log_stream=resource_prefix
        ),
        vpc_id=vpc_stack.get_output("vpc_id"),
        security_group_ids=[vpn_sg.id],
        session_timeout_hours=1,
        self_service_portal="enabled",
        server_certificate_arn=vpn_server_cert.certificate_arn,
        split_tunnel=True,
        tags={
            "Name": f"{resource_prefix}",
        },
        opts=pulumi.ResourceOptions(depends_on=[vpn_cw_loggroup, vpn_cw_logstream, vpn_server_cert])
    )

    return vpn

def configure_vpn(vpn):
    def create_vpn_auth_rule_all_groups():
        aws.ec2clientvpn.AuthorizationRule(f"{resource_prefix}-auth-rule-all-groups",
            client_vpn_endpoint_id=vpn.id,
            target_network_cidr="0.0.0.0/0",
            authorize_all_groups=True
        )
    
    def create_vpn_network_association(subnet_id):
        vpn_network_association = aws.ec2clientvpn.NetworkAssociation(f"{resource_prefix}-network-association-{subnet_id}",
            client_vpn_endpoint_id=vpn.id,
            subnet_id=subnet_id
        )
        return vpn_network_association
    
    def create_vpn_associations(subnet_ids):
        for subnet_id in subnet_ids:
            create_vpn_network_association(subnet_id)
    vpc_stack.get_output("private_subnet_ids").apply(lambda private_subnet_ids: create_vpn_associations(private_subnet_ids))
    create_vpn_auth_rule_all_groups()

vpn = create_vpn()
configure_vpn(vpn)

