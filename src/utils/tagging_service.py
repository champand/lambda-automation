"""
Tagging Service Module
=====================

Handles applying tags to AWS resources across multiple services.
Implements service-specific tagging logic and batch operations where supported.
"""

import logging
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from .retry_utils import retry_with_exponential_backoff
from .excel_parser import extract_tags_from_row, get_resource_info

logger = logging.getLogger(__name__)


def apply_tags_to_resource(
    row_data: Dict[str, Any],
    sheet_name: str,
    session_credentials: Dict[str, str],
    region: str
) -> Dict[str, Any]:
    """
    Apply tags to a single resource.

    Args:
        row_data: Row data containing resource info and tags
        sheet_name: Name of the sheet (used for resource type)
        session_credentials: Temporary AWS credentials
        region: AWS region

    Returns:
        Dictionary with tagging result:
        {
            'status': 'SUCCESS' | 'FAILED' | 'PARTIAL' | 'SKIPPED',
            'tags_applied': [list of tag keys],
            'error_message': str (if failed)
        }
    """
    # Extract resource information
    resource_info = get_resource_info(row_data)

    # Extract tags to apply
    tags_to_apply = extract_tags_from_row(row_data)

    if not tags_to_apply:
        return {
            'status': 'SKIPPED',
            'tags_applied': [],
            'error_message': 'No tags to apply'
        }

    # Determine resource type
    resource_type = resource_info.get('resourceType', sheet_name).upper()

    # Get target region (from row data or default)
    target_region = resource_info.get('awsRegion', region)

    logger.debug(f"Applying {len(tags_to_apply)} tags to {resource_type} resource")

    try:
        # Route to appropriate service-specific tagging function
        if resource_type in ['EC2', 'EBS', 'NAT', 'VPC']:
            result = tag_ec2_resource(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type == 'S3':
            result = tag_s3_bucket(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type == 'RDS':
            result = tag_rds_resource(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type == 'EKS':
            result = tag_eks_cluster(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type in ['LB', 'ELB', 'ALB', 'NLB']:
            result = tag_load_balancer(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type == 'ELASTICACHE':
            result = tag_elasticache_resource(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type in ['OPENSEARCH', 'ES']:
            result = tag_opensearch_domain(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type == 'MSK':
            result = tag_msk_cluster(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type == 'CLOUDFRONT':
            result = tag_cloudfront_distribution(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type == 'SAGEMAKER':
            result = tag_sagemaker_resource(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type == 'DOCDB':
            result = tag_docdb_cluster(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type == 'REDSHIFT':
            result = tag_redshift_cluster(resource_info, tags_to_apply, session_credentials, target_region)

        elif resource_type == 'GLUE':
            result = tag_glue_resource(resource_info, tags_to_apply, session_credentials, target_region)

        else:
            # Try generic resource groups tagging API
            result = tag_using_resource_groups_api(resource_info, tags_to_apply, session_credentials, target_region)

        return result

    except Exception as e:
        logger.error(f"Unexpected error tagging resource: {str(e)}")
        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': f"Unexpected error: {str(e)}"
        }


@retry_with_exponential_backoff(max_retries=3)
def tag_ec2_resource(
    resource_info: Dict[str, str],
    tags: Dict[str, str],
    credentials: Dict[str, str],
    region: str
) -> Dict[str, Any]:
    """Tag EC2 resources (instances, volumes, VPCs, etc.)"""

    ec2_client = boto3.client(
        'ec2',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    # Get resource ID (either from ARN or resourceId)
    resource_id = None

    if resource_info.get('arn'):
        # Parse resource ID from ARN
        arn_parts = resource_info['arn'].split(':')
        if len(arn_parts) >= 6:
            resource_id = arn_parts[-1].split('/')[-1]
    else:
        resource_id = resource_info.get('resourceId')

    if not resource_id:
        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': 'Could not determine EC2 resource ID'
        }

    try:
        # Convert tags to EC2 format
        ec2_tags = [{'Key': k, 'Value': v} for k, v in tags.items()]

        # Apply tags
        ec2_client.create_tags(
            Resources=[resource_id],
            Tags=ec2_tags
        )

        logger.info(f"Successfully tagged EC2 resource {resource_id}")

        return {
            'status': 'SUCCESS',
            'tags_applied': list(tags.keys()),
            'error_message': None
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')

        logger.error(f"Failed to tag EC2 resource {resource_id}: {error_code} - {error_message}")

        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': f"{error_code}: {error_message}"
        }


@retry_with_exponential_backoff(max_retries=3)
def tag_s3_bucket(
    resource_info: Dict[str, str],
    tags: Dict[str, str],
    credentials: Dict[str, str],
    region: str
) -> Dict[str, Any]:
    """Tag S3 bucket"""

    s3_client = boto3.client(
        's3',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    # Get bucket name
    bucket_name = None

    if resource_info.get('arn'):
        # Parse bucket name from ARN (arn:aws:s3:::bucket-name)
        bucket_name = resource_info['arn'].split(':::')[-1].split('/')[0]
    else:
        bucket_name = resource_info.get('resourceId')

    if not bucket_name:
        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': 'Could not determine S3 bucket name'
        }

    try:
        # Get existing tags
        try:
            existing_tags_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
            existing_tags = {tag['Key']: tag['Value'] for tag in existing_tags_response.get('TagSet', [])}
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'NoSuchTagSet':
                existing_tags = {}
            else:
                raise

        # Merge with new tags (new tags override existing)
        merged_tags = {**existing_tags, **tags}

        # Convert to S3 format
        s3_tags = [{'Key': k, 'Value': v} for k, v in merged_tags.items()]

        # Apply tags
        s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={'TagSet': s3_tags}
        )

        logger.info(f"Successfully tagged S3 bucket {bucket_name}")

        return {
            'status': 'SUCCESS',
            'tags_applied': list(tags.keys()),
            'error_message': None
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')

        logger.error(f"Failed to tag S3 bucket {bucket_name}: {error_code} - {error_message}")

        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': f"{error_code}: {error_message}"
        }


@retry_with_exponential_backoff(max_retries=3)
def tag_rds_resource(
    resource_info: Dict[str, str],
    tags: Dict[str, str],
    credentials: Dict[str, str],
    region: str
) -> Dict[str, Any]:
    """Tag RDS resource (DB instance, cluster, etc.)"""

    rds_client = boto3.client(
        'rds',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    # Get resource ARN
    resource_arn = resource_info.get('arn')

    if not resource_arn:
        # Construct ARN if not provided
        account_id = credentials['AccountId']
        resource_id = resource_info.get('resourceId')

        if not resource_id:
            return {
                'status': 'FAILED',
                'tags_applied': [],
                'error_message': 'Could not determine RDS resource ARN or ID'
            }

        resource_arn = f"arn:aws:rds:{region}:{account_id}:db:{resource_id}"

    try:
        # Convert tags to RDS format
        rds_tags = [{'Key': k, 'Value': v} for k, v in tags.items()]

        # Apply tags
        rds_client.add_tags_to_resource(
            ResourceName=resource_arn,
            Tags=rds_tags
        )

        logger.info(f"Successfully tagged RDS resource {resource_arn}")

        return {
            'status': 'SUCCESS',
            'tags_applied': list(tags.keys()),
            'error_message': None
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')

        logger.error(f"Failed to tag RDS resource: {error_code} - {error_message}")

        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': f"{error_code}: {error_message}"
        }


@retry_with_exponential_backoff(max_retries=3)
def tag_eks_cluster(
    resource_info: Dict[str, str],
    tags: Dict[str, str],
    credentials: Dict[str, str],
    region: str
) -> Dict[str, Any]:
    """Tag EKS cluster"""

    eks_client = boto3.client(
        'eks',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    # Get cluster ARN or name
    resource_arn = resource_info.get('arn')
    cluster_name = None

    if resource_arn:
        # Use ARN directly
        pass
    else:
        cluster_name = resource_info.get('resourceId')
        if not cluster_name:
            return {
                'status': 'FAILED',
                'tags_applied': [],
                'error_message': 'Could not determine EKS cluster name or ARN'
            }

        # Construct ARN
        account_id = credentials['AccountId']
        resource_arn = f"arn:aws:eks:{region}:{account_id}:cluster/{cluster_name}"

    try:
        # Apply tags
        eks_client.tag_resource(
            resourceArn=resource_arn,
            tags=tags
        )

        logger.info(f"Successfully tagged EKS cluster {resource_arn}")

        return {
            'status': 'SUCCESS',
            'tags_applied': list(tags.keys()),
            'error_message': None
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')

        logger.error(f"Failed to tag EKS cluster: {error_code} - {error_message}")

        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': f"{error_code}: {error_message}"
        }


@retry_with_exponential_backoff(max_retries=3)
def tag_load_balancer(
    resource_info: Dict[str, str],
    tags: Dict[str, str],
    credentials: Dict[str, str],
    region: str
) -> Dict[str, Any]:
    """Tag ELB/ALB/NLB"""

    elbv2_client = boto3.client(
        'elbv2',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    resource_arn = resource_info.get('arn')

    if not resource_arn:
        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': 'Load balancer ARN is required for tagging'
        }

    try:
        # Convert tags to ELB format
        elb_tags = [{'Key': k, 'Value': v} for k, v in tags.items()]

        # Apply tags
        elbv2_client.add_tags(
            ResourceArns=[resource_arn],
            Tags=elb_tags
        )

        logger.info(f"Successfully tagged load balancer {resource_arn}")

        return {
            'status': 'SUCCESS',
            'tags_applied': list(tags.keys()),
            'error_message': None
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')

        logger.error(f"Failed to tag load balancer: {error_code} - {error_message}")

        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': f"{error_code}: {error_message}"
        }


@retry_with_exponential_backoff(max_retries=3)
def tag_elasticache_resource(
    resource_info: Dict[str, str],
    tags: Dict[str, str],
    credentials: Dict[str, str],
    region: str
) -> Dict[str, Any]:
    """Tag ElastiCache resource"""

    elasticache_client = boto3.client(
        'elasticache',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    resource_arn = resource_info.get('arn')

    if not resource_arn:
        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': 'ElastiCache resource ARN is required'
        }

    try:
        # Convert tags
        ec_tags = [{'Key': k, 'Value': v} for k, v in tags.items()]

        # Apply tags
        elasticache_client.add_tags_to_resource(
            ResourceName=resource_arn,
            Tags=ec_tags
        )

        logger.info(f"Successfully tagged ElastiCache resource {resource_arn}")

        return {
            'status': 'SUCCESS',
            'tags_applied': list(tags.keys()),
            'error_message': None
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')

        logger.error(f"Failed to tag ElastiCache resource: {error_code} - {error_message}")

        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': f"{error_code}: {error_message}"
        }


def tag_opensearch_domain(resource_info, tags, credentials, region):
    """Tag OpenSearch domain"""
    return tag_using_resource_groups_api(resource_info, tags, credentials, region)


def tag_msk_cluster(resource_info, tags, credentials, region):
    """Tag MSK cluster"""
    return tag_using_resource_groups_api(resource_info, tags, credentials, region)


def tag_cloudfront_distribution(resource_info, tags, credentials, region):
    """Tag CloudFront distribution"""
    return tag_using_resource_groups_api(resource_info, tags, credentials, region)


def tag_sagemaker_resource(resource_info, tags, credentials, region):
    """Tag SageMaker resource"""
    return tag_using_resource_groups_api(resource_info, tags, credentials, region)


def tag_docdb_cluster(resource_info, tags, credentials, region):
    """Tag DocumentDB cluster"""
    return tag_using_resource_groups_api(resource_info, tags, credentials, region)


def tag_redshift_cluster(resource_info, tags, credentials, region):
    """Tag Redshift cluster"""
    return tag_using_resource_groups_api(resource_info, tags, credentials, region)


def tag_glue_resource(resource_info, tags, credentials, region):
    """Tag Glue resource"""
    return tag_using_resource_groups_api(resource_info, tags, credentials, region)


@retry_with_exponential_backoff(max_retries=3)
def tag_using_resource_groups_api(
    resource_info: Dict[str, str],
    tags: Dict[str, str],
    credentials: Dict[str, str],
    region: str
) -> Dict[str, Any]:
    """
    Tag resource using Resource Groups Tagging API (cross-service).

    This is a fallback method that works for many AWS services.
    """

    tagging_client = boto3.client(
        'resourcegroupstaggingapi',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    resource_arn = resource_info.get('arn')

    if not resource_arn:
        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': 'Resource ARN is required for Resource Groups Tagging API'
        }

    try:
        # Apply tags
        response = tagging_client.tag_resources(
            ResourceARNList=[resource_arn],
            Tags=tags
        )

        # Check for failures
        failed_resources = response.get('FailedResourcesMap', {})

        if failed_resources:
            error_info = failed_resources.get(resource_arn, {})
            error_code = error_info.get('ErrorCode', 'Unknown')
            error_message = error_info.get('ErrorMessage', 'Unknown error')

            logger.error(f"Failed to tag resource via Resource Groups API: {error_code} - {error_message}")

            return {
                'status': 'FAILED',
                'tags_applied': [],
                'error_message': f"{error_code}: {error_message}"
            }

        logger.info(f"Successfully tagged resource {resource_arn} via Resource Groups API")

        return {
            'status': 'SUCCESS',
            'tags_applied': list(tags.keys()),
            'error_message': None
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')

        logger.error(f"Failed to tag resource via Resource Groups API: {error_code} - {error_message}")

        return {
            'status': 'FAILED',
            'tags_applied': [],
            'error_message': f"{error_code}: {error_message}"
        }


@retry_with_exponential_backoff(max_retries=3)
def batch_tag_resources(
    resources: List[str],
    tags: Dict[str, str],
    credentials: Dict[str, str],
    region: str
) -> Dict[str, Any]:
    """
    Batch tag multiple resources using Resource Groups Tagging API.

    Args:
        resources: List of resource ARNs
        tags: Tags to apply
        credentials: AWS credentials
        region: AWS region

    Returns:
        Dictionary with batch tagging results
    """
    tagging_client = boto3.client(
        'resourcegroupstaggingapi',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )

    successful = []
    failed = []

    # Process in batches of 20 (API limit)
    batch_size = 20

    for i in range(0, len(resources), batch_size):
        batch = resources[i:i + batch_size]

        try:
            response = tagging_client.tag_resources(
                ResourceARNList=batch,
                Tags=tags
            )

            # Check for failures
            failed_resources = response.get('FailedResourcesMap', {})

            for arn in batch:
                if arn in failed_resources:
                    failed.append({
                        'arn': arn,
                        'error': failed_resources[arn]
                    })
                else:
                    successful.append(arn)

        except ClientError as e:
            logger.error(f"Batch tagging failed: {str(e)}")
            for arn in batch:
                failed.append({
                    'arn': arn,
                    'error': str(e)
                })

    return {
        'successful': successful,
        'failed': failed,
        'total': len(resources)
    }
