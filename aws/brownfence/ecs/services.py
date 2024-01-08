import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx

def create(cluster):

    def createAlbSecurityGroup():
        alb_sg = aws.ec2.SecurityGroup("brownfence-alb-sg",
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
                "Name": "brownfence-alb-sg",
            })
        
        return alb_sg
    
    def createServiceSecurityGroup(alb_sg_id):
        services_sg = aws.ec2.SecurityGroup("brownfence-services-sg",
            description="Allow all traffic from ALB and this SG",
            vpc_id=aws.ec2.get_vpc(default=True),
            ingress=[aws.ec2.SecurityGroupIngressArgs(
                description="allow all traffic from alb & this sg",
                from_port=0,
                to_port=0,
                protocol="-1",
                security_groups=[alb_sg_id],
                self=True
            )],
            egress=[aws.ec2.SecurityGroupEgressArgs(
                from_port=0,
                to_port=0,
                protocol="-1",
                cidr_blocks=["0.0.0.0/0"],
                ipv6_cidr_blocks=["::/0"],
            )],
            tags={
                "Name": "brownfence-services-sg",
            })
        
        return services_sg
    
    def createNextcloudService():
        f

    alb_sg = createAlbSecurityGroup()
    createServiceSecurityGroup(alb_sg.id)
        
