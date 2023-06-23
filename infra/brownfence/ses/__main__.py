import pulumi
import pulumi_aws as aws

config = pulumi.Config()
ses_domain = config.require("ses_domain")

# Make sure we are deploying to Santorakubik:
if aws.get_caller_identity().account_id != "927123100668":
    print(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")
    exit()

# Create SES domain identity
# Note: We use us-east-1 for SES for max compatibility
colerange_ses_domain_identity = aws.ses.DomainIdentity("colerange_ses_domain_identity", domain="colerange.us")

# Add SES verification record to Route53
colerange_ses_verification_record = aws.route53.Record("colerange_ses_verification_record",
    zone_id=aws.route53.get_zone(name="colerange.us").zone_id,
    name=colerange_ses_domain_identity.id.apply(lambda id: f"_amazonses.{id}"),
    type="TXT",
    ttl=600,
    records=[colerange_ses_domain_identity.verification_token]
)
colerange_ses_domain_identity_verification = aws.ses.DomainIdentityVerification("colerange_ses_domain_identity_verification", domain=colerange_ses_domain_identity.id)

# Create IAM user for SES SMTP access
ses_smtp_user = aws.iam.User("ses_smtp_user", name="ses_smtp_user")
ses_smtp_user_access_key = aws.iam.AccessKey("ses_smtp_user_access_key", user=ses_smtp_user.name)
ses_smtp_user_policy_document = aws.iam.get_policy_document(statements=[aws.iam.GetPolicyDocumentStatementArgs(
    effect="Allow",
    actions=["ses:SendRawEmail"],
    resources=["*"],
)])
ses_smtp_user_policy = aws.iam.UserPolicy("ses_smtp_user_policy",
    user=ses_smtp_user.name,
    policy=ses_smtp_user_policy_document.json
)
# Store SES SMTP creds in SSM (in us-east-2, our default region for app)
aws_east_2 = aws.Provider('aws-east-2', region='us-east-2')
aws.ssm.Parameter("ssm_ses_smtp_username", 
    type="String", 
    name="/nextcloud/smtp/username", 
    value=ses_smtp_user_access_key.id, 
    opts=pulumi.ResourceOptions(provider=aws_east_2)
)
aws.ssm.Parameter("ssm_ses_smtp_password", 
    type="SecureString", 
    name="/nextcloud/smtp/password", 
    value=ses_smtp_user_access_key.ses_smtp_password_v4,
    opts=pulumi.ResourceOptions(provider=aws_east_2)
)
