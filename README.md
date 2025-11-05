# AWS Lambda Resource Tagging Automation

Production-ready AWS Lambda function that automates cost-allocation tagging across multiple AWS accounts using an Excel input file.

## 🎯 Overview

This Lambda function enables centralized, automated tagging of AWS resources across member accounts from a delegated management account. It reads resource information and tag specifications from an Excel file stored in S3, applies tags using cross-account role assumption, generates comprehensive reports, and sends notifications via SNS.

### Key Features

- ✅ **Multi-Account Support**: Assumes roles in member accounts for cross-account tagging
- ✅ **20+ AWS Services**: Supports EC2, S3, RDS, EKS, ElastiCache, OpenSearch, MSK, CloudFront, and more
- ✅ **Excel-Based Input**: Multi-sheet Excel files with flexible column naming
- ✅ **Comprehensive Reporting**: Generates detailed Excel reports with success/failure status
- ✅ **Presigned Download Links**: 4-hour expiring S3 presigned URLs for report downloads
- ✅ **SNS Notifications**: Well-formatted email notifications with execution summaries
- ✅ **Retry Logic**: Exponential backoff with jitter for AWS API throttling
- ✅ **Production-Ready**: Extensive error handling, logging, and idempotency
- ✅ **Security**: Least-privilege IAM policies, encrypted S3 storage
- ✅ **Testable**: Unit tests with pytest, mocking for AWS services

## 📋 Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Usage](#usage)
- [Input File Format](#input-file-format)
- [Output Reports](#output-reports)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [IAM Permissions](#iam-permissions)
- [Security Considerations](#security-considerations)

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────┐      ┌─────────────────┐
│  S3 Bucket      │ ───> │   Lambda     │ ───> │ Member Account  │
│  (Input Excel)  │      │   Function   │      │  Resources      │
└─────────────────┘      └──────────────┘      └─────────────────┘
                               │                         │
                               │ STS AssumeRole          │
                               v                         v
                         ┌──────────┐             ┌─────────┐
                         │   SNS    │             │  Tags   │
                         │  Topic   │             │ Applied │
                         └──────────┘             └─────────┘
                               │
                               v
                         ┌──────────────┐
                         │ Report Excel │
                         │  in S3       │
                         └──────────────┘
```

**Flow:**
1. Lambda triggered manually or on schedule
2. Downloads Excel file from S3
3. Parses sheets and validates rows
4. For each row, assumes role in member account
5. Applies tags using service-specific APIs
6. Generates comprehensive Excel report
7. Uploads report to S3 with presigned URL
8. Sends SNS notification with summary

## 📦 Prerequisites

### Management Account
- AWS Account ID: `673343607675` (delegated management account)
- IAM role for Lambda execution: `DelegatedTaggingExecutionRole`
- S3 bucket for input/output files
- SNS topic for notifications

### Member Accounts
- IAM role: `MemberTaggingRole` (trusts management account)
- Cross-account trust policy configured

### Local Development
- Python 3.12+
- pip
- AWS CLI configured with appropriate credentials
- (Optional) Docker for Lambda layer building

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd lambda-automation
```

### 2. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (for testing)
pip install -r requirements-dev.txt
```

### 3. Run Unit Tests

```bash
pytest tests/ -v
```

### 4. Create Sample Input File

```bash
cd examples
python create_sample_input.py
# Creates: sample_tagging_input.xlsx
```

### 5. Deploy Infrastructure

See [Deployment](#deployment) section below.

## 🚢 Deployment

### Step 1: Deploy Management Account Resources

```bash
cd cloudformation

aws cloudformation deploy \
  --template-file management-account-roles.yaml \
  --stack-name lambda-tagging-automation \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      S3BucketName=my-tagging-bucket \
      SNSTopicName=tagging-notifications \
      MemberRoleName=MemberTaggingRole \
      LambdaFunctionName=ResourceTaggingAutomation
```

**Outputs:**
- Lambda Execution Role ARN
- S3 Bucket Name
- SNS Topic ARN

### Step 2: Deploy Member Account Roles

Deploy this stack in **EACH** member account:

```bash
aws cloudformation deploy \
  --template-file member-account-role.yaml \
  --stack-name tagging-member-role \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      ManagementAccountId=673343607675 \
      ManagementRoleName=DelegatedTaggingExecutionRole \
      MemberRoleName=MemberTaggingRole \
  --profile <member-account-profile>
```

### Step 3: Package Lambda Code

```bash
# From project root
./scripts/package_lambda.sh

# Creates: lambda-deployment-package.zip
```

### Step 4: Deploy Lambda Function

```bash
aws lambda update-function-code \
  --function-name ResourceTaggingAutomation \
  --zip-file fileb://lambda-deployment-package.zip
```

### Step 5: Configure Environment Variables

```bash
aws lambda update-function-configuration \
  --function-name ResourceTaggingAutomation \
  --environment Variables="{
    REGION=ap-south-1,
    S3_BUCKET=my-tagging-bucket,
    TAGGING_INPUT_FILE=input/tagging_input.xlsx,
    TAGGING_REPORT_FILE_PREFIX=reports/tagging_report_,
    SNS_TOPIC_ARN=arn:aws:sns:ap-south-1:673343607675:tagging-notifications,
    LOG_LEVEL=INFO,
    AWS_ACCOUNT_IDS='123456789012,987654321098',
    PRESIGNED_URL_EXPIRY=14400,
    MEMBER_ROLE_NAME=MemberTaggingRole
  }"
```

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REGION` | No | `ap-south-1` | AWS region for Lambda execution |
| `S3_BUCKET` | **Yes** | - | S3 bucket for input/output files |
| `TAGGING_INPUT_FILE` | **Yes** | - | S3 key for input Excel file |
| `TAGGING_REPORT_FILE_PREFIX` | **Yes** | - | Prefix for output report files |
| `SNS_TOPIC_ARN` | **Yes** | - | SNS topic for notifications |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `AWS_ACCOUNT_IDS` | No | `` | Comma-separated account IDs to process |
| `PRESIGNED_URL_EXPIRY` | No | `14400` | Presigned URL expiry in seconds (4 hours) |
| `MEMBER_ROLE_NAME` | **Yes** | - | IAM role name in member accounts |
| `EXECUTION_ROLE_ARN` | No | - | Lambda execution role ARN (documentation) |

### Lambda Configuration

- **Runtime**: Python 3.12
- **Memory**: 512 MB (adjust based on workload)
- **Timeout**: 900 seconds (15 minutes)
- **Handler**: `lambda_function.tag_resources_lambda.lambda_handler`

## 📊 Usage

### Manual Invocation

```bash
aws lambda invoke \
  --function-name ResourceTaggingAutomation \
  --payload '{}' \
  response.json

cat response.json
```

### Scheduled Execution (EventBridge)

```bash
aws events put-rule \
  --name TaggingAutomationSchedule \
  --schedule-expression "cron(0 2 * * ? *)"  # Daily at 2 AM UTC

aws events put-targets \
  --rule TaggingAutomationSchedule \
  --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:ResourceTaggingAutomation"

aws lambda add-permission \
  --function-name ResourceTaggingAutomation \
  --statement-id EventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:REGION:ACCOUNT:rule/TaggingAutomationSchedule
```

### S3 Trigger (on file upload)

```bash
aws s3api put-bucket-notification-configuration \
  --bucket my-tagging-bucket \
  --notification-configuration file://s3-notification.json
```

`s3-notification.json`:
```json
{
  "LambdaFunctionConfigurations": [
    {
      "LambdaFunctionArn": "arn:aws:lambda:REGION:ACCOUNT:function:ResourceTaggingAutomation",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "prefix", "Value": "input/"},
            {"Name": "suffix", "Value": ".xlsx"}
          ]
        }
      }
    }
  ]
}
```

## 📄 Input File Format

### Excel Structure

The input Excel file should have multiple sheets, one per AWS resource type:

**Supported Sheet Names:**
- EC2, EBS, NAT, S3, LB, RDS, EKS, Glue, Prometheus, VPC, Firewall, MSK, OpenSearch, SageMaker, DocDB, GuardDuty, SecurityHub, ElastiCache, RedShift, CloudFront

### Required Columns

**Option 1: Using ARN**
- `arn` - Full AWS Resource ARN
- Tag columns (e.g., `pl:cost-allocation:environment`)

**Option 2: Using Resource Identifiers**
- `accountId` - AWS Account ID (12 digits)
- `resourceType` - Resource type (defaults to sheet name)
- `resourceId` - Resource identifier (instance ID, bucket name, etc.)
- `awsRegion` - AWS region (e.g., `us-east-1`)
- Tag columns

### Column Aliases

The parser recognizes these column name variations:

| Standard | Aliases |
|----------|---------|
| `arn` | `ARN`, `resource_arn`, `ResourceARN` |
| `accountId` | `account_id`, `Account`, `aws_account_id` |
| `resourceType` | `resource_type`, `Type`, `service` |
| `resourceId` | `resource_id`, `Id`, `resource_identifier` |
| `awsRegion` | `aws_region`, `Region`, `region` |

### Tag Columns

Tag columns are identified by:
- Prefix `pl:cost-allocation:`
- Prefix `tag:`
- Common names: `environment`, `cost_center`, `project`, `owner`, `team`

### Example Sheet (EC2)

| arn | accountId | resourceId | awsRegion | pl:cost-allocation:environment | pl:cost-allocation:team | pl:cost-allocation:project |
|-----|-----------|------------|-----------|-------------------------------|------------------------|---------------------------|
| arn:aws:ec2:us-east-1:123456789012:instance/i-12345 | 123456789012 | i-12345 | us-east-1 | production | platform | web-app |
| | 987654321098 | i-67890 | us-west-2 | development | backend | api-service |

## 📈 Output Reports

### Report Structure

Reports are Excel files with two sheets:

#### Summary Sheet
- Execution metadata (ID, timestamp, version)
- Overall statistics (total, success, failed, partial, skipped)
- Success rate
- Breakdown by resource type

#### Details Sheet
| Column | Description |
|--------|-------------|
| Timestamp | When row was processed |
| Sheet Name | Source sheet |
| Row Number | Original row number |
| Account ID | AWS account |
| Resource Type | Resource type |
| Resource ID | Resource identifier |
| ARN | Resource ARN |
| Region | AWS region |
| Status | SUCCESS / FAILED / PARTIAL / SKIPPED |
| Tags Applied | Comma-separated tag keys |
| Tags Count | Number of tags applied |
| Error Message | Error details (if failed) |

### Report Location

Reports are uploaded to S3 with naming convention:
```
s3://<bucket>/<prefix><execution-id>.xlsx
```

Example:
```
s3://my-tagging-bucket/reports/tagging_report_exec-20250105-143022.xlsx
```

### Presigned URL

The SNS notification includes a presigned download URL valid for 4 hours (configurable).

## 🧪 Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test Module

```bash
pytest tests/test_config_validator.py -v
```

### Run with Coverage

```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests (requires AWS credentials)
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

### Mock AWS Services

Tests use `moto` for mocking AWS services. Example:

```python
from moto import mock_s3, mock_sts
import boto3

@mock_s3
@mock_sts
def test_cross_account_tagging():
    # Create mock S3 bucket
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket='test-bucket')

    # Test your function
    result = tag_resources_lambda.lambda_handler({}, {})
    assert result['statusCode'] == 200
```

## 🔍 Troubleshooting

### Common Issues

#### 1. "AccessDenied" when assuming role

**Cause**: Trust policy or permissions issue in member account.

**Solution**:
- Verify `MemberTaggingRole` exists in member account
- Check trust policy allows management account role
- Verify role has tagging permissions

```bash
# Check role in member account
aws iam get-role --role-name MemberTaggingRole --profile member-account
```

#### 2. "File not found in S3"

**Cause**: Input file path incorrect or missing.

**Solution**:
- Verify S3 bucket and key in environment variables
- Check file exists: `aws s3 ls s3://bucket/path/to/file.xlsx`
- Ensure Lambda role has `s3:GetObject` permission

#### 3. Tags not being applied

**Cause**: Missing permissions in member account role.

**Solution**:
- Check CloudWatch Logs for specific error
- Verify member role has service-specific tagging permissions
- Test with Resource Groups Tagging API first

#### 4. Presigned URL not working

**Cause**: Signature mismatch or expired URL.

**Solution**:
- Ensure S3 client uses `signature_version='s3v4'`
- Check `PRESIGNED_URL_EXPIRY` is reasonable
- Verify S3 bucket is in same region as Lambda

### Debugging

#### Enable Debug Logging

```bash
aws lambda update-function-configuration \
  --function-name ResourceTaggingAutomation \
  --environment Variables="{LOG_LEVEL=DEBUG,...}"
```

#### View CloudWatch Logs

```bash
aws logs tail /aws/lambda/ResourceTaggingAutomation --follow
```

#### Test Locally

```python
# test_local.py
import os
os.environ['REGION'] = 'us-east-1'
os.environ['S3_BUCKET'] = 'my-bucket'
# ... set other env vars

from src.lambda_function.tag_resources_lambda import lambda_handler

result = lambda_handler({}, None)
print(result)
```

## 🔒 IAM Permissions

### Management Account Lambda Role

Minimum permissions:
- `s3:GetObject`, `s3:PutObject` on tagging bucket
- `sts:AssumeRole` on member account roles
- `sns:Publish` on notification topic
- `logs:CreateLogStream`, `logs:PutLogEvents` on log group

See: `cloudformation/management-account-roles.yaml`

### Member Account Role

Minimum permissions per service:
- **EC2**: `ec2:CreateTags`, `ec2:DescribeInstances`
- **S3**: `s3:PutBucketTagging`, `s3:GetBucketTagging`
- **RDS**: `rds:AddTagsToResource`, `rds:DescribeDBInstances`
- **Cross-Service**: `resourcegroupstaggingapi:TagResources`

See: `cloudformation/member-account-role.yaml`

### Least-Privilege Recommendations

1. **Scope by Resource**: Use resource-level permissions where possible
2. **Condition Keys**: Add conditions for MFA, source IP, etc.
3. **Session Duration**: Keep AssumeRole duration short (1 hour)
4. **External ID**: Use external ID in trust policy for additional security
5. **Audit**: Enable CloudTrail for all tagging operations

## 🛡️ Security Considerations

### Data Security
- ✅ S3 bucket encryption enabled (AES-256)
- ✅ S3 bucket versioning enabled
- ✅ S3 public access blocked
- ✅ Presigned URLs expire after 4 hours
- ✅ Temporary credentials for cross-account access

### Access Control
- ✅ Least-privilege IAM policies
- ✅ Cross-account role assumption with trust policy
- ✅ Optional external ID in trust policy
- ✅ Session duration limited to 1 hour

### Audit & Compliance
- ✅ CloudWatch Logs retention (30 days)
- ✅ CloudTrail logging recommended
- ✅ SNS notifications for all executions
- ✅ Detailed report generation

### Secrets Management
- ⚠️ **Never** commit AWS credentials to code
- ⚠️ **Never** log sensitive data (credentials, ARNs with account IDs)
- ✅ Use IAM roles for authentication
- ✅ Store sensitive config in Parameter Store / Secrets Manager

## 📚 Additional Resources

- [AWS Resource Groups Tagging API](https://docs.aws.amazon.com/resourcegroupstagging/latest/APIReference/)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Cross-Account IAM Roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_cross-account-with-roles.html)
- [Cost Allocation Tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest tests/ -v`
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 👥 Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Contact: cloud-engineering-team@example.com

---

**Version**: 1.0.0
**Last Updated**: 2025-01-05
**Maintained by**: Cloud Engineering Team
