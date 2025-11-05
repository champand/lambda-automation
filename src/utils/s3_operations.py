"""
S3 Operations Module
===================

Handles all S3 operations including downloading Excel files, uploading reports,
and generating presigned URLs.
"""

import os
import logging
import tempfile
from typing import Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .retry_utils import retry_with_exponential_backoff

logger = logging.getLogger(__name__)


def get_s3_client(region: str):
    """
    Create S3 client with proper configuration for presigned URLs.

    Uses signature version s3v4 to ensure presigned URLs work cross-region.

    Args:
        region: AWS region

    Returns:
        Configured boto3 S3 client
    """
    config = Config(
        region_name=region,
        signature_version='s3v4',
        retries={
            'max_attempts': 3,
            'mode': 'standard'
        }
    )
    return boto3.client('s3', config=config)


@retry_with_exponential_backoff(max_retries=4)
def download_excel_from_s3(bucket: str, key: str, region: str) -> str:
    """
    Download Excel file from S3 to local temp directory.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        region: AWS region

    Returns:
        Path to downloaded file

    Raises:
        ClientError: If download fails
        FileNotFoundError: If file doesn't exist in S3
    """
    logger.info(f"Downloading s3://{bucket}/{key}")

    s3_client = get_s3_client(region)

    # Check if file exists
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            raise FileNotFoundError(f"File not found in S3: s3://{bucket}/{key}")
        raise

    # Create temp file with appropriate extension
    file_extension = os.path.splitext(key)[1] or '.xlsx'
    temp_fd, temp_path = tempfile.mkstemp(suffix=file_extension, prefix='tagging_input_')

    try:
        # Download file
        with os.fdopen(temp_fd, 'wb') as temp_file:
            s3_client.download_fileobj(bucket, key, temp_file)

        logger.info(f"Successfully downloaded to {temp_path}")
        return temp_path

    except Exception as e:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        logger.error(f"Failed to download from S3: {str(e)}")
        raise


@retry_with_exponential_backoff(max_retries=4)
def upload_report_to_s3(report_content: bytes, bucket: str, key: str, region: str) -> None:
    """
    Upload report file to S3.

    Args:
        report_content: Report content as bytes
        bucket: S3 bucket name
        key: S3 object key
        region: AWS region

    Raises:
        ClientError: If upload fails
    """
    logger.info(f"Uploading report to s3://{bucket}/{key}")

    s3_client = get_s3_client(region)

    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=report_content,
            ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ServerSideEncryption='AES256',  # Enable encryption at rest
            Metadata={
                'generated-by': 'lambda-tagging-automation',
                'content-type': 'tagging-report'
            }
        )
        logger.info(f"Successfully uploaded report to S3")

    except ClientError as e:
        logger.error(f"Failed to upload report to S3: {str(e)}")
        raise


def generate_presigned_url(bucket: str, key: str, expiry: int, region: str) -> str:
    """
    Generate presigned URL for S3 object download.

    Uses S3v4 signature for cross-region compatibility.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        expiry: URL expiry time in seconds
        region: AWS region

    Returns:
        Presigned URL string

    Raises:
        ClientError: If URL generation fails
    """
    logger.info(f"Generating presigned URL for s3://{bucket}/{key} (expiry: {expiry}s)")

    s3_client = get_s3_client(region)

    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key
            },
            ExpiresIn=expiry,
            HttpMethod='GET'
        )

        logger.info("Presigned URL generated successfully")
        return presigned_url

    except ClientError as e:
        logger.error(f"Failed to generate presigned URL: {str(e)}")
        raise


def check_s3_bucket_exists(bucket: str, region: str) -> bool:
    """
    Check if S3 bucket exists and is accessible.

    Args:
        bucket: S3 bucket name
        region: AWS region

    Returns:
        True if bucket exists and is accessible, False otherwise
    """
    s3_client = get_s3_client(region)

    try:
        s3_client.head_bucket(Bucket=bucket)
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            logger.error(f"Bucket does not exist: {bucket}")
        elif error_code == '403':
            logger.error(f"Access denied to bucket: {bucket}")
        else:
            logger.error(f"Error checking bucket: {str(e)}")
        return False


def get_bucket_region(bucket: str, default_region: str) -> str:
    """
    Get the region of an S3 bucket.

    Args:
        bucket: S3 bucket name
        default_region: Default region to use if detection fails

    Returns:
        Bucket region
    """
    try:
        s3_client = boto3.client('s3', region_name=default_region)
        response = s3_client.get_bucket_location(Bucket=bucket)

        # None means us-east-1
        bucket_region = response.get('LocationConstraint') or 'us-east-1'
        return bucket_region

    except ClientError as e:
        logger.warning(f"Could not determine bucket region: {str(e)}")
        return default_region
