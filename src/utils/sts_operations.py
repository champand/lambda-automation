"""
STS Operations Module
====================

Handles AWS Security Token Service (STS) operations for assuming roles
in member accounts.
"""

import logging
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from .retry_utils import retry_with_exponential_backoff

logger = logging.getLogger(__name__)


@retry_with_exponential_backoff(max_retries=3)
def assume_member_role(
    account_id: str,
    role_name: str,
    session_name: str,
    region: str,
    duration_seconds: int = 3600
) -> Dict[str, str]:
    """
    Assume IAM role in member account using STS.

    Args:
        account_id: Target AWS account ID
        role_name: IAM role name to assume
        session_name: Session name for the assumed role
        region: AWS region
        duration_seconds: Session duration (default: 3600s = 1 hour)

    Returns:
        Dictionary containing temporary credentials:
        {
            'AccessKeyId': '...',
            'SecretAccessKey': '...',
            'SessionToken': '...',
            'AccountId': '...'
        }

    Raises:
        ClientError: If role assumption fails
        ValueError: If parameters are invalid
    """
    # Validate inputs
    if not account_id or len(account_id) != 12 or not account_id.isdigit():
        raise ValueError(f"Invalid account ID: {account_id}")

    if not role_name:
        raise ValueError("Role name cannot be empty")

    # Construct role ARN
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    logger.info(f"Assuming role: {role_arn}")

    # Create STS client
    config = Config(
        region_name=region,
        retries={'max_attempts': 3, 'mode': 'standard'}
    )
    sts_client = boto3.client('sts', config=config)

    try:
        # Assume role
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            DurationSeconds=duration_seconds
        )

        credentials = response['Credentials']

        logger.info(f"Successfully assumed role in account {account_id}")

        return {
            'AccessKeyId': credentials['AccessKeyId'],
            'SecretAccessKey': credentials['SecretAccessKey'],
            'SessionToken': credentials['SessionToken'],
            'AccountId': account_id,
            'Expiration': credentials['Expiration'].isoformat()
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')

        if error_code == 'AccessDenied':
            logger.error(f"Access denied assuming role {role_arn}: {error_message}")
            raise ClientError(
                {
                    'Error': {
                        'Code': 'AccessDenied',
                        'Message': f"Cannot assume role {role_name} in account {account_id}. "
                                 f"Check trust policy and permissions."
                    }
                },
                'AssumeRole'
            )
        else:
            logger.error(f"Failed to assume role {role_arn}: {error_code} - {error_message}")
            raise


def get_session_clients(
    credentials: Dict[str, str],
    region: str,
    services: list = None
) -> Dict[str, Any]:
    """
    Create boto3 clients for specified services using temporary credentials.

    Args:
        credentials: Temporary credentials from assume_role
        region: AWS region
        services: List of AWS service names (default: common tagging services)

    Returns:
        Dictionary mapping service names to boto3 clients
    """
    if services is None:
        # Default services commonly used for tagging
        services = [
            'ec2',
            's3',
            'rds',
            'eks',
            'elasticache',
            'opensearch',
            'kafka',  # MSK
            'cloudfront',
            'elbv2',  # Load Balancers
            'resourcegroupstaggingapi'
        ]

    clients = {}

    config = Config(
        region_name=region,
        retries={'max_attempts': 3, 'mode': 'standard'}
    )

    for service in services:
        try:
            client = boto3.client(
                service,
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                config=config
            )
            clients[service] = client
            logger.debug(f"Created {service} client for account {credentials['AccountId']}")

        except Exception as e:
            logger.warning(f"Failed to create {service} client: {str(e)}")

    return clients


def get_caller_identity(region: str = 'us-east-1') -> Dict[str, str]:
    """
    Get current AWS identity information.

    Args:
        region: AWS region (default: us-east-1)

    Returns:
        Dictionary with Account, UserId, and Arn
    """
    sts_client = boto3.client('sts', region_name=region)

    try:
        response = sts_client.get_caller_identity()
        return {
            'Account': response['Account'],
            'UserId': response['UserId'],
            'Arn': response['Arn']
        }
    except ClientError as e:
        logger.error(f"Failed to get caller identity: {str(e)}")
        raise


def validate_cross_account_access(
    account_id: str,
    role_name: str,
    region: str
) -> Dict[str, Any]:
    """
    Validate that cross-account role can be assumed.

    Args:
        account_id: Target account ID
        role_name: Role name to validate
        region: AWS region

    Returns:
        Dictionary with validation result:
        {
            'valid': bool,
            'error': str (if not valid),
            'role_arn': str
        }
    """
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    try:
        # Attempt to assume role with minimal duration
        credentials = assume_member_role(
            account_id=account_id,
            role_name=role_name,
            session_name='validation-test',
            region=region,
            duration_seconds=900  # Minimum 15 minutes
        )

        return {
            'valid': True,
            'role_arn': role_arn,
            'message': 'Successfully validated cross-account access'
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')

        return {
            'valid': False,
            'role_arn': role_arn,
            'error': f"{error_code}: {error_message}"
        }


def create_session_from_credentials(
    credentials: Dict[str, str],
    region: str
):
    """
    Create boto3 session from temporary credentials.

    Args:
        credentials: Temporary credentials dictionary
        region: AWS region

    Returns:
        boto3.Session object
    """
    session = boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    return session
