import json
import pulumi_aws as aws

managed_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
]

# Creates a role and attaches the EKS worker node IAM managed policies
def create_cluster_role(name: str) -> aws.iam.Role:
    role = aws.iam.Role(name, assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowAssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com",
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }))

    for i, policy in enumerate(managed_policy_arns):
        # Create RolePolicyAttachment without returning it.
        rpa = aws.iam.RolePolicyAttachment(f"{name}-policy-{i}",
            policy_arn=policy,
            role=role.id
        )

    return role

def create_cluster_lb_controller_role() -> aws.iam.Role:
    # create policy
    fp = open('files/aws_load_balancer_controller_iam_policy.json', 'r')
    policy_data = fp.read()
    policy = aws.iam.Policy("lb-controller-policy",
        path="/",
        description="brownfence eks cluster alb controller policy",
        policy=policy_data
    )

    fp = open('files/aws_load_balancer_role_trust_policy.json', 'r')
    assume_role_policy_data = fp.read()
    role = aws.iam.Role("lb-controller-role", assume_role_policy=assume_role_policy_data)
    aws.iam.RolePolicyAttachment("lb-role-attachment",
        role=role.name,
        policy_arn=policy.arn
    )

    fp.close()
    return role



