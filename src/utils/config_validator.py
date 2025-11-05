"""
Configuration Validator Module
==============================

Validates and parses environment variables required for Lambda execution.
Ensures all required configuration is present and properly formatted.
"""

import os
import re
import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

# AWS Account ID regex pattern (12 digits)
ACCOUNT_ID_PATTERN = re.compile(r'^\d{12}$')

# AWS ARN pattern (basic validation)
ARN_PATTERN = re.compile(r'^arn:aws:[\w\-]+:[\w\-]*:\d{12}:.*$')


def validate_environment_config() -> Dict[str, any]:
    """
    Validates all required environment variables and returns configuration dict.

    Required environment variables:
    - REGION: AWS region (default: ap-south-1)
    - S3_BUCKET: S3 bucket for input/output files
    - TAGGING_INPUT_FILE: Input Excel filename
    - TAGGING_REPORT_FILE_PREFIX: Output report filename prefix
    - SNS_TOPIC_ARN: SNS topic for notifications
    - MEMBER_ROLE_NAME: IAM role name in member accounts
    - AWS_ACCOUNT_IDS: Comma-separated account IDs (optional, defaults to empty)

    Returns:
        Dict containing validated configuration

    Raises:
        ValueError: If required config is missing or invalid
    """
    config = {}

    # Region (default: ap-south-1)
    config['region'] = os.environ.get('REGION', 'ap-south-1').strip()
    if not config['region']:
        raise ValueError("REGION cannot be empty")
    logger.debug(f"Region: {config['region']}")

    # S3 Bucket (required)
    config['s3_bucket'] = os.environ.get('S3_BUCKET', '').strip()
    if not config['s3_bucket']:
        raise ValueError("S3_BUCKET environment variable is required")
    logger.debug(f"S3 Bucket: {config['s3_bucket']}")

    # Input file (required)
    config['input_file'] = os.environ.get('TAGGING_INPUT_FILE', '').strip()
    if not config['input_file']:
        raise ValueError("TAGGING_INPUT_FILE environment variable is required")
    logger.debug(f"Input file: {config['input_file']}")

    # Report file prefix (required)
    config['report_prefix'] = os.environ.get('TAGGING_REPORT_FILE_PREFIX', '').strip()
    if not config['report_prefix']:
        raise ValueError("TAGGING_REPORT_FILE_PREFIX environment variable is required")
    # Ensure prefix ends with / or - for clean filenames
    if not config['report_prefix'].endswith(('/','_', '-')):
        config['report_prefix'] += '_'
    logger.debug(f"Report prefix: {config['report_prefix']}")

    # SNS Topic ARN (required)
    config['sns_topic_arn'] = os.environ.get('SNS_TOPIC_ARN', '').strip()
    if not config['sns_topic_arn']:
        raise ValueError("SNS_TOPIC_ARN environment variable is required")
    if not config['sns_topic_arn'].startswith('arn:aws:sns:'):
        raise ValueError(f"Invalid SNS_TOPIC_ARN format: {config['sns_topic_arn']}")
    logger.debug(f"SNS Topic ARN: {config['sns_topic_arn']}")

    # Member role name (required)
    config['member_role_name'] = os.environ.get('MEMBER_ROLE_NAME', '').strip()
    if not config['member_role_name']:
        raise ValueError("MEMBER_ROLE_NAME environment variable is required")
    logger.debug(f"Member role name: {config['member_role_name']}")

    # AWS Account IDs (optional, comma-separated)
    account_ids_str = os.environ.get('AWS_ACCOUNT_IDS', '').strip()
    config['account_ids'] = parse_account_ids(account_ids_str)
    logger.debug(f"Target account IDs: {config['account_ids']}")

    # Presigned URL expiry (default: 14400 seconds = 4 hours)
    try:
        config['presigned_expiry'] = int(os.environ.get('PRESIGNED_URL_EXPIRY', '14400'))
        if config['presigned_expiry'] <= 0:
            raise ValueError("PRESIGNED_URL_EXPIRY must be positive")
        if config['presigned_expiry'] > 604800:  # Max 7 days
            logger.warning(f"PRESIGNED_URL_EXPIRY of {config['presigned_expiry']}s exceeds 7 days, using 7 days")
            config['presigned_expiry'] = 604800
    except ValueError as e:
        raise ValueError(f"Invalid PRESIGNED_URL_EXPIRY: {e}")
    logger.debug(f"Presigned URL expiry: {config['presigned_expiry']}s")

    # Execution role ARN (optional, for documentation)
    config['execution_role_arn'] = os.environ.get('EXECUTION_ROLE_ARN', '').strip()

    logger.info("Environment configuration validated successfully")
    return config


def parse_account_ids(account_ids_str: str) -> Set[str]:
    """
    Parse and validate comma-separated AWS account IDs.

    Args:
        account_ids_str: Comma-separated string of account IDs

    Returns:
        Set of validated account IDs

    Raises:
        ValueError: If any account ID is invalid
    """
    if not account_ids_str:
        return set()

    account_ids = set()
    for account_id in account_ids_str.split(','):
        account_id = account_id.strip()
        if not account_id:
            continue

        # Validate account ID format (12 digits)
        if not ACCOUNT_ID_PATTERN.match(account_id):
            raise ValueError(f"Invalid AWS account ID format: {account_id}")

        account_ids.add(account_id)

    return account_ids


def validate_arn(arn: str) -> bool:
    """
    Validate AWS ARN format.

    Args:
        arn: AWS ARN string

    Returns:
        True if valid, False otherwise
    """
    if not arn:
        return False
    return bool(ARN_PATTERN.match(arn))


def validate_resource_id(resource_id: str, resource_type: str) -> bool:
    """
    Validate resource ID format based on resource type.

    Args:
        resource_id: Resource identifier
        resource_type: Type of AWS resource

    Returns:
        True if valid format, False otherwise
    """
    if not resource_id:
        return False

    # Basic validation - ensure not empty and reasonable length
    if len(resource_id) < 1 or len(resource_id) > 256:
        return False

    # Resource-specific validation patterns
    resource_patterns = {
        'EC2': re.compile(r'^(i-[0-9a-f]{8,17})$'),
        'EBS': re.compile(r'^(vol-[0-9a-f]{8,17})$'),
        'S3': re.compile(r'^[a-z0-9][a-z0-9\-\.]{1,61}[a-z0-9]$'),
        'RDS': re.compile(r'^[a-zA-Z][a-zA-Z0-9\-]{0,62}$'),
        'EKS': re.compile(r'^[a-zA-Z][a-zA-Z0-9\-]{0,99}$'),
    }

    pattern = resource_patterns.get(resource_type.upper())
    if pattern:
        return bool(pattern.match(resource_id))

    # For unknown types, basic validation only
    return len(resource_id) > 0


def parse_tags_from_row(row_data: Dict[str, any]) -> Dict[str, str]:
    """
    Extract tag key-value pairs from row data.

    Tags are identified by keys starting with 'pl:cost-allocation:' or 'tag:'.

    Args:
        row_data: Dictionary containing row data

    Returns:
        Dictionary of tag keys and values
    """
    tags = {}

    for key, value in row_data.items():
        # Check if key looks like a tag column
        if key and (
            key.startswith('pl:cost-allocation:') or
            key.startswith('tag:') or
            key.lower() in ['environment', 'cost_center', 'project', 'owner', 'team']
        ):
            # Skip if value is None or empty
            if value is None or (isinstance(value, str) and not value.strip()):
                continue

            # Convert value to string and strip whitespace
            tag_value = str(value).strip()

            # Skip empty values
            if not tag_value or tag_value.lower() in ['none', 'null', 'n/a', '']:
                continue

            tags[key] = tag_value

    return tags
