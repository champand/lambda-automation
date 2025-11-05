# Deployment Guide

Complete step-by-step guide for deploying the AWS Lambda Resource Tagging Automation system.

## Prerequisites

### AWS Accounts
- **Management Account**: 673343607675 (delegated management)
- **Member Accounts**: List of accounts where resources will be tagged

### Required Tools
- AWS CLI v2
- Python 3.12+
- Git
- jq (optional, for JSON parsing)

### AWS Credentials
Configure AWS CLI profiles:

```bash
# Management account
aws configure --profile management-account
# Enter access key, secret key, region

# Member accounts (repeat for each)
aws configure --profile member-account-1
aws configure --profile member-account-2
```

## Deployment Steps

### Phase 1: Management Account Setup

#### 1.1 Clone Repository

```bash
git clone <repository-url>
cd lambda-automation
```

#### 1.2 Create S3 Bucket

```bash
BUCKET_NAME="tagging-automation-$(date +%s)"

aws s3 mb s3://${BUCKET_NAME} \
  --region ap-south-1 \
  --profile management-account

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket ${BUCKET_NAME} \
  --versioning-configuration Status=Enabled \
  --profile management-account

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket ${BUCKET_NAME} \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }' \
  --profile management-account

echo "✓ S3 bucket created: ${BUCKET_NAME}"
```

#### 1.3 Deploy CloudFormation Stack

```bash
aws cloudformation deploy \
  --template-file cloudformation/management-account-roles.yaml \
  --stack-name lambda-tagging-automation \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      S3BucketName=${BUCKET_NAME} \
      SNSTopicName=tagging-automation-notifications \
      MemberRoleName=MemberTaggingRole \
      LambdaFunctionName=ResourceTaggingAutomation \
  --profile management-account \
  --region ap-south-1

echo "✓ Management account stack deployed"
```

#### 1.4 Get Stack Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name lambda-tagging-automation \
  --query 'Stacks[0].Outputs' \
  --profile management-account \
  --region ap-south-1 \
  --output table
```

Save these values:
- `LambdaExecutionRoleArn`
- `LambdaFunctionArn`
- `SNSTopicArn`
- `S3BucketName`

#### 1.5 Subscribe to SNS Topic

```bash
SNS_TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name lambda-tagging-automation \
  --query 'Stacks[0].Outputs[?OutputKey==`SNSTopicArn`].OutputValue' \
  --output text \
  --profile management-account \
  --region ap-south-1)

aws sns subscribe \
  --topic-arn ${SNS_TOPIC_ARN} \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --profile management-account \
  --region ap-south-1

echo "✓ SNS subscription created - check your email to confirm"
```

### Phase 2: Member Account Setup

Deploy the member account role in **EACH** member account.

#### 2.1 Deploy Member Role (Account 1)

```bash
MEMBER_ACCOUNT_1="123456789012"

aws cloudformation deploy \
  --template-file cloudformation/member-account-role.yaml \
  --stack-name tagging-member-role \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      ManagementAccountId=673343607675 \
      ManagementRoleName=DelegatedTaggingExecutionRole \
      MemberRoleName=MemberTaggingRole \
  --profile member-account-1 \
  --region ap-south-1

echo "✓ Member role deployed in account ${MEMBER_ACCOUNT_1}"
```

#### 2.2 Verify Role Trust Policy

```bash
aws iam get-role \
  --role-name MemberTaggingRole \
  --profile member-account-1 \
  --query 'Role.AssumeRolePolicyDocument' \
  --output json
```

Verify the trust policy allows:
```json
{
  "Principal": {
    "AWS": "arn:aws:iam::673343607675:role/DelegatedTaggingExecutionRole"
  }
}
```

#### 2.3 Repeat for Additional Member Accounts

```bash
# Account 2
aws cloudformation deploy \
  --template-file cloudformation/member-account-role.yaml \
  --stack-name tagging-member-role \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides ManagementAccountId=673343607675 \
  --profile member-account-2 \
  --region ap-south-1

# Add more accounts as needed
```

### Phase 3: Lambda Deployment

#### 3.1 Install Dependencies

```bash
pip install -r requirements.txt
```

#### 3.2 Run Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v

# All tests should pass
```

#### 3.3 Build Deployment Package

```bash
./scripts/package_lambda.sh
```

Output: `lambda-deployment-package.zip`

#### 3.4 Deploy Lambda Code

```bash
aws lambda update-function-code \
  --function-name ResourceTaggingAutomation \
  --zip-file fileb://lambda-deployment-package.zip \
  --profile management-account \
  --region ap-south-1

echo "✓ Lambda code deployed"
```

#### 3.5 Configure Environment Variables

Create a file `lambda-env.json`:

```json
{
  "Variables": {
    "REGION": "ap-south-1",
    "S3_BUCKET": "YOUR_BUCKET_NAME",
    "TAGGING_INPUT_FILE": "input/tagging_input.xlsx",
    "TAGGING_REPORT_FILE_PREFIX": "reports/tagging_report_",
    "SNS_TOPIC_ARN": "YOUR_SNS_TOPIC_ARN",
    "LOG_LEVEL": "INFO",
    "AWS_ACCOUNT_IDS": "123456789012,987654321098",
    "PRESIGNED_URL_EXPIRY": "14400",
    "MEMBER_ROLE_NAME": "MemberTaggingRole"
  }
}
```

Apply configuration:

```bash
aws lambda update-function-configuration \
  --function-name ResourceTaggingAutomation \
  --environment file://lambda-env.json \
  --profile management-account \
  --region ap-south-1

echo "✓ Environment variables configured"
```

### Phase 4: Testing

#### 4.1 Create Sample Input File

```bash
cd examples
python3 create_sample_input.py

# Creates: sample_tagging_input.xlsx
```

#### 4.2 Upload to S3

```bash
aws s3 cp sample_tagging_input.xlsx \
  s3://${BUCKET_NAME}/input/tagging_input.xlsx \
  --profile management-account \
  --region ap-south-1

echo "✓ Sample input uploaded"
```

#### 4.3 Test Lambda Function

```bash
aws lambda invoke \
  --function-name ResourceTaggingAutomation \
  --payload '{}' \
  --profile management-account \
  --region ap-south-1 \
  response.json

cat response.json | jq .
```

Expected output:
```json
{
  "statusCode": 200,
  "body": {
    "status": "SUCCESS",
    "execution_id": "exec-20250105-143022",
    "summary": {
      "total": 10,
      "success": 8,
      "failed": 1,
      "partial": 0,
      "skipped": 1
    },
    "report_location": "s3://...",
    "presigned_url": "https://..."
  }
}
```

#### 4.4 Check CloudWatch Logs

```bash
aws logs tail /aws/lambda/ResourceTaggingAutomation \
  --follow \
  --profile management-account \
  --region ap-south-1
```

#### 4.5 Download Report

Check your email for SNS notification with presigned URL, or:

```bash
# List reports
aws s3 ls s3://${BUCKET_NAME}/reports/ \
  --profile management-account

# Download latest report
aws s3 cp s3://${BUCKET_NAME}/reports/tagging_report_<execution-id>.xlsx . \
  --profile management-account
```

### Phase 5: Production Configuration

#### 5.1 Set Up Scheduled Execution

```bash
# Create EventBridge rule
aws events put-rule \
  --name TaggingAutomationDaily \
  --schedule-expression "cron(0 2 * * ? *)" \
  --description "Run tagging automation daily at 2 AM UTC" \
  --profile management-account \
  --region ap-south-1

# Get Lambda ARN
LAMBDA_ARN=$(aws cloudformation describe-stacks \
  --stack-name lambda-tagging-automation \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionArn`].OutputValue' \
  --output text \
  --profile management-account \
  --region ap-south-1)

# Add Lambda as target
aws events put-targets \
  --rule TaggingAutomationDaily \
  --targets "Id"="1","Arn"="${LAMBDA_ARN}" \
  --profile management-account \
  --region ap-south-1

# Grant EventBridge permission
aws lambda add-permission \
  --function-name ResourceTaggingAutomation \
  --statement-id EventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:ap-south-1:673343607675:rule/TaggingAutomationDaily" \
  --profile management-account \
  --region ap-south-1

echo "✓ Scheduled execution configured"
```

#### 5.2 Configure CloudWatch Alarms

```bash
# Alarm for Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name TaggingLambda-Errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=ResourceTaggingAutomation \
  --alarm-actions ${SNS_TOPIC_ARN} \
  --profile management-account \
  --region ap-south-1

echo "✓ CloudWatch alarms configured"
```

#### 5.3 Enable CloudTrail Logging

```bash
# Create CloudTrail for tagging API calls
aws cloudtrail create-trail \
  --name tagging-automation-trail \
  --s3-bucket-name ${BUCKET_NAME} \
  --is-multi-region-trail \
  --enable-log-file-validation \
  --profile management-account \
  --region ap-south-1

aws cloudtrail start-logging \
  --name tagging-automation-trail \
  --profile management-account \
  --region ap-south-1

echo "✓ CloudTrail logging enabled"
```

## Post-Deployment Checklist

- [ ] Management account stack deployed
- [ ] Member account roles deployed in all accounts
- [ ] Lambda code deployed and tested
- [ ] Environment variables configured
- [ ] SNS email subscription confirmed
- [ ] Sample execution successful
- [ ] Reports generated correctly
- [ ] Presigned URLs work
- [ ] CloudWatch logs accessible
- [ ] Scheduled execution configured (if needed)
- [ ] CloudWatch alarms set up
- [ ] CloudTrail enabled for audit

## Verification Commands

```bash
# Check Lambda configuration
aws lambda get-function-configuration \
  --function-name ResourceTaggingAutomation \
  --profile management-account \
  --region ap-south-1

# Check IAM role
aws iam get-role \
  --role-name DelegatedTaggingExecutionRole \
  --profile management-account

# List S3 bucket contents
aws s3 ls s3://${BUCKET_NAME}/ --recursive \
  --profile management-account

# Check SNS subscriptions
aws sns list-subscriptions-by-topic \
  --topic-arn ${SNS_TOPIC_ARN} \
  --profile management-account \
  --region ap-south-1
```

## Rollback Procedure

If issues occur:

```bash
# Delete Lambda function
aws lambda delete-function \
  --function-name ResourceTaggingAutomation \
  --profile management-account

# Delete CloudFormation stacks
aws cloudformation delete-stack \
  --stack-name lambda-tagging-automation \
  --profile management-account

# Member accounts
aws cloudformation delete-stack \
  --stack-name tagging-member-role \
  --profile member-account-1

# Empty and delete S3 bucket
aws s3 rm s3://${BUCKET_NAME} --recursive
aws s3 rb s3://${BUCKET_NAME}
```

## Troubleshooting

See [Troubleshooting Guide](./TROUBLESHOOTING.md) for common issues and solutions.

## Support

For deployment issues, contact: cloud-engineering-team@example.com
