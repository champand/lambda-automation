# Project Structure

```
lambda-automation/
├── README.md                          # Main documentation
├── PROJECT_STRUCTURE.md               # This file
├── .gitignore                         # Git ignore patterns
├── requirements.txt                   # Production dependencies
├── requirements-dev.txt               # Development dependencies
├── pytest.ini                         # Pytest configuration
│
├── src/                               # Source code
│   ├── lambda_function/               # Lambda handler
│   │   └── tag_resources_lambda.py   # Main Lambda entry point
│   │
│   └── utils/                         # Utility modules
│       ├── __init__.py
│       ├── config_validator.py        # Environment validation
│       ├── s3_operations.py           # S3 download/upload/presigned URLs
│       ├── excel_parser.py            # Excel parsing logic
│       ├── sts_operations.py          # Cross-account role assumption
│       ├── tagging_service.py         # Service-specific tagging
│       ├── report_generator.py        # Excel report generation
│       ├── sns_operations.py          # SNS notifications
│       └── retry_utils.py             # Exponential backoff retry logic
│
├── tests/                             # Unit tests
│   ├── __init__.py
│   ├── test_config_validator.py       # Config validation tests
│   ├── test_excel_parser.py           # Excel parsing tests
│   └── test_retry_utils.py            # Retry logic tests
│
├── cloudformation/                    # Infrastructure as Code
│   ├── management-account-roles.yaml  # Management account resources
│   └── member-account-role.yaml       # Member account IAM role
│
├── scripts/                           # Deployment scripts
│   └── package_lambda.sh              # Build deployment package
│
├── examples/                          # Example files
│   └── create_sample_input.py         # Generate sample Excel input
│
└── docs/                              # Additional documentation
    └── DEPLOYMENT_GUIDE.md            # Step-by-step deployment guide
```

## Module Descriptions

### Core Lambda Function

**`src/lambda_function/tag_resources_lambda.py`**
- Main Lambda handler (`lambda_handler`)
- Orchestrates the entire tagging workflow
- Coordinates between utility modules
- Handles error scenarios and notifications

### Utility Modules

**`src/utils/config_validator.py`**
- Validates environment variables
- Parses account IDs
- Validates ARNs and resource IDs
- Extracts tags from row data

**`src/utils/s3_operations.py`**
- Downloads Excel files from S3
- Uploads reports to S3
- Generates presigned URLs (S3v4 signature)
- Handles S3 bucket operations

**`src/utils/excel_parser.py`**
- Parses multi-sheet Excel files
- Normalizes column names
- Validates row data
- Extracts resource information and tags

**`src/utils/sts_operations.py`**
- Assumes IAM roles in member accounts
- Creates session-scoped AWS clients
- Validates cross-account access
- Manages temporary credentials

**`src/utils/tagging_service.py`**
- Routes to service-specific tagging functions
- Implements tagging for 20+ AWS services:
  - EC2, EBS, VPC
  - S3
  - RDS
  - EKS
  - ElastiCache
  - OpenSearch
  - MSK
  - CloudFront
  - Load Balancers (ALB/NLB)
  - SageMaker
  - DocumentDB
  - Redshift
  - Glue
  - And more...
- Batch tagging with Resource Groups Tagging API

**`src/utils/report_generator.py`**
- Creates multi-sheet Excel reports
- Generates summary statistics
- Formats details with color coding
- Exports to Excel format (openpyxl)

**`src/utils/sns_operations.py`**
- Sends formatted SNS notifications
- Creates human-readable messages
- Includes presigned URLs in notifications
- Handles error notifications

**`src/utils/retry_utils.py`**
- Exponential backoff with jitter
- Detects retryable errors
- Decorator-based retry logic
- Batch processing with retries

### CloudFormation Templates

**`cloudformation/management-account-roles.yaml`**
Creates in management account (673343607675):
- Lambda execution role
- S3 bucket for input/output
- SNS topic for notifications
- CloudWatch log group
- Lambda function (placeholder)

**`cloudformation/member-account-role.yaml`**
Creates in each member account:
- Cross-account IAM role
- Trust policy for management account
- Service-specific tagging permissions
- Least-privilege IAM policies

### Tests

**`tests/test_config_validator.py`**
- Environment variable validation
- Account ID parsing
- ARN validation
- Tag extraction from rows

**`tests/test_excel_parser.py`**
- Column name normalization
- Cell value cleaning
- Row validation
- Resource info extraction

**`tests/test_retry_utils.py`**
- Retryable error detection
- Backoff delay calculation
- Retry decorator behavior
- Non-retryable error handling

### Scripts

**`scripts/package_lambda.sh`**
- Builds deployment package
- Installs dependencies
- Copies source code
- Creates ZIP file
- Validates package contents

### Examples

**`examples/create_sample_input.py`**
- Generates sample Excel input file
- Multiple sheets (EC2, S3, RDS, EKS, etc.)
- Example tag columns
- Demonstrates expected format

### Documentation

**`README.md`**
- Project overview
- Quick start guide
- Configuration reference
- Usage instructions
- Troubleshooting

**`docs/DEPLOYMENT_GUIDE.md`**
- Step-by-step deployment
- Prerequisites
- Phase-by-phase instructions
- Verification commands
- Post-deployment checklist

## Key Features by Module

| Feature | Module |
|---------|--------|
| Excel parsing | `excel_parser.py` |
| S3 operations | `s3_operations.py` |
| Cross-account access | `sts_operations.py` |
| Resource tagging | `tagging_service.py` |
| Report generation | `report_generator.py` |
| Notifications | `sns_operations.py` |
| Retry logic | `retry_utils.py` |
| Configuration | `config_validator.py` |
| Main workflow | `tag_resources_lambda.py` |

## Data Flow

```
1. Lambda Triggered
   ↓
2. config_validator validates environment
   ↓
3. s3_operations downloads Excel from S3
   ↓
4. excel_parser parses sheets and rows
   ↓
5. For each row:
   ├─ sts_operations assumes member role
   ├─ tagging_service applies tags
   └─ report_generator records result
   ↓
6. report_generator finalizes Excel report
   ↓
7. s3_operations uploads report to S3
   ↓
8. s3_operations generates presigned URL
   ↓
9. sns_operations sends notification
   ↓
10. Lambda returns success/failure
```

## Extension Points

### Adding New AWS Services

1. Add service-specific function in `tagging_service.py`
2. Add service name to routing in `apply_tags_to_resource()`
3. Add IAM permissions to `member-account-role.yaml`
4. Add tests if needed

### Custom Tag Validation

Modify `config_validator.parse_tags_from_row()` to add custom validation logic.

### Custom Report Formats

Extend `report_generator.py` to support CSV, JSON, or other formats.

### Additional Notification Channels

Add functions in `sns_operations.py` or create new module for Slack, Teams, etc.

## Development Workflow

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Make changes to source code
vim src/utils/tagging_service.py

# Run tests
pytest tests/ -v

# Run specific test
pytest tests/test_tagging_service.py::TestEC2Tagging -v

# Check coverage
pytest tests/ --cov=src --cov-report=html

# Package for deployment
./scripts/package_lambda.sh

# Deploy
aws lambda update-function-code \
  --function-name ResourceTaggingAutomation \
  --zip-file fileb://lambda-deployment-package.zip
```

## Security Notes

- Never commit AWS credentials
- Use IAM roles for all AWS access
- Enable CloudTrail for audit logging
- Review IAM policies regularly
- Use encryption at rest (S3)
- Limit presigned URL expiry
- Rotate member account roles periodically

## Performance Considerations

- Batch operations where possible
- Use paginators for large result sets
- Implement exponential backoff for throttling
- Consider Lambda timeout (15 min max)
- Monitor memory usage
- Optimize package size (<50MB uncompressed)

## Monitoring

**CloudWatch Metrics:**
- Lambda invocations
- Lambda errors
- Lambda duration
- Lambda concurrent executions

**CloudWatch Logs:**
- `/aws/lambda/ResourceTaggingAutomation`

**Custom Metrics:**
- Total resources processed
- Success/failure counts
- Tagging latency per service

**Alarms:**
- Lambda errors > 0
- Lambda duration > 10 minutes
- Failed tagging operations

## Maintenance

### Regular Tasks
- [ ] Review CloudWatch logs weekly
- [ ] Check SNS notifications
- [ ] Verify report accuracy
- [ ] Update dependencies monthly
- [ ] Review IAM permissions quarterly
- [ ] Rotate credentials annually

### Updates
- Update `requirements.txt` for new boto3 versions
- Update CloudFormation templates for new services
- Add tests for new functionality
- Update documentation

## Support

For questions or issues:
1. Check README troubleshooting section
2. Review CloudWatch logs
3. Consult DEPLOYMENT_GUIDE.md
4. Contact: cloud-engineering-team@example.com
