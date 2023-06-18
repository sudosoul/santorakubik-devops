import pulumi
import pulumi_aws as aws

config = pulumi.Config()
ses_domain = config.require("ses_domain")

# Make sure we are deploying to Santorakubik:
if aws.get_caller_identity().account_id != "927123100668":
    print(f"ERROR: IN WRONG AWS ACCOUNT!\nCurrent ID:{aws.get_caller_identity().account_id}")
    exit()

# Create SES domain identity
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

