"""
SNS Operations Module
====================

Handles SNS notifications with formatted messages containing tagging results.
"""

import logging
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from .retry_utils import retry_with_exponential_backoff

logger = logging.getLogger(__name__)


@retry_with_exponential_backoff(max_retries=3)
def send_tagging_notification(
    topic_arn: str,
    summary_stats: Dict[str, Any],
    presigned_url: str,
    report_location: str,
    region: str
) -> Dict[str, Any]:
    """
    Send SNS notification with tagging results.

    Args:
        topic_arn: SNS topic ARN
        summary_stats: Dictionary containing execution statistics
        presigned_url: Presigned URL for report download
        report_location: S3 location of report
        region: AWS region

    Returns:
        SNS publish response

    Raises:
        ClientError: If SNS publish fails
    """
    logger.info(f"Sending SNS notification to {topic_arn}")

    # Create SNS client
    config = Config(
        region_name=region,
        retries={'max_attempts': 3, 'mode': 'standard'}
    )
    sns_client = boto3.client('sns', config=config)

    # Format message
    subject, message = _format_notification_message(summary_stats, presigned_url, report_location)

    try:
        # Publish to SNS
        response = sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message,
            MessageStructure='string'
        )

        logger.info(f"SNS notification sent successfully. MessageId: {response['MessageId']}")
        return response

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')

        logger.error(f"Failed to send SNS notification: {error_code} - {error_message}")
        raise


def _format_notification_message(
    summary_stats: Dict[str, Any],
    presigned_url: str,
    report_location: str
) -> tuple:
    """
    Format notification message with summary and download link.

    Args:
        summary_stats: Execution statistics
        presigned_url: Presigned URL for report
        report_location: S3 location

    Returns:
        Tuple of (subject, message)
    """
    execution_id = summary_stats.get('execution_id', 'unknown')
    total = summary_stats.get('total_rows', 0)
    successful = summary_stats.get('successful', 0)
    failed = summary_stats.get('failed', 0)
    partial = summary_stats.get('partial', 0)
    skipped = summary_stats.get('skipped', 0)

    # Calculate success rate
    success_rate = (successful / total * 100) if total > 0 else 0

    # Determine status emoji
    if failed == 0 and partial == 0:
        status_emoji = "✅"
        status_text = "SUCCESS"
    elif successful == 0:
        status_emoji = "❌"
        status_text = "FAILED"
    else:
        status_emoji = "⚠️"
        status_text = "PARTIAL SUCCESS"

    # Subject line
    subject = f"{status_emoji} AWS Resource Tagging - {status_text} - {execution_id}"

    # Message body
    message = f"""
AWS Resource Tagging Automation Report
{'=' * 50}

Execution ID: {execution_id}
Status: {status_text}
Timestamp: {summary_stats.get('end_time', 'N/A')}

SUMMARY STATISTICS
{'=' * 50}
Total Resources Processed:  {total}
✅ Successful:               {successful}
❌ Failed:                   {failed}
⚠️  Partial:                 {partial}
⏭️  Skipped:                 {skipped}
📊 Success Rate:             {success_rate:.1f}%

REPORT DETAILS
{'=' * 50}
S3 Location: {report_location}

📥 Download Report (expires in 4 hours):
{presigned_url}

"""

    # Add failure summary if there are failures
    if failed > 0 or partial > 0:
        message += f"""
⚠️  ACTION REQUIRED
{'=' * 50}
{failed + partial} resource(s) require attention.
Please review the detailed report for error messages and take corrective action.

Common Issues:
- Access Denied: Check IAM role permissions in member accounts
- Invalid Resource ID: Verify resource exists and identifiers are correct
- Throttling: Resources will be retried automatically

"""

    message += """
NEXT STEPS
{'=' * 50}
1. Download the detailed Excel report using the link above
2. Review the 'Details' sheet for per-resource status
3. Address any failed resources and re-run if needed
4. Archive this report for compliance and audit purposes

For support, contact your Cloud Engineering team.
"""

    return subject, message.strip()


def send_error_notification(
    topic_arn: str,
    execution_id: str,
    error_message: str,
    region: str
) -> Dict[str, Any]:
    """
    Send error notification when Lambda execution fails.

    Args:
        topic_arn: SNS topic ARN
        execution_id: Execution ID
        error_message: Error message
        region: AWS region

    Returns:
        SNS publish response
    """
    logger.info(f"Sending error notification to {topic_arn}")

    config = Config(
        region_name=region,
        retries={'max_attempts': 3, 'mode': 'standard'}
    )
    sns_client = boto3.client('sns', config=config)

    subject = f"❌ AWS Resource Tagging - EXECUTION FAILED - {execution_id}"

    message = f"""
AWS Resource Tagging Automation - EXECUTION FAILED
{'=' * 50}

Execution ID: {execution_id}
Status: FAILED
Timestamp: {summary_stats.get('timestamp', 'N/A')}

ERROR DETAILS
{'=' * 50}
{error_message}

ACTION REQUIRED
{'=' * 50}
The tagging Lambda function encountered a fatal error and could not complete.

Please check:
1. CloudWatch Logs for detailed error traces
2. Environment variable configuration
3. S3 bucket and input file accessibility
4. IAM role permissions

For immediate assistance, contact your Cloud Engineering team.
"""

    try:
        response = sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message.strip(),
            MessageStructure='string'
        )

        logger.info(f"Error notification sent successfully. MessageId: {response['MessageId']}")
        return response

    except ClientError as e:
        logger.error(f"Failed to send error notification: {str(e)}")
        # Don't raise - this is a best-effort notification
        return {}


def validate_sns_topic(topic_arn: str, region: str) -> bool:
    """
    Validate that SNS topic exists and is accessible.

    Args:
        topic_arn: SNS topic ARN
        region: AWS region

    Returns:
        True if topic is valid, False otherwise
    """
    sns_client = boto3.client('sns', region_name=region)

    try:
        sns_client.get_topic_attributes(TopicArn=topic_arn)
        logger.info(f"SNS topic validated: {topic_arn}")
        return True

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')

        if error_code == 'NotFound':
            logger.error(f"SNS topic not found: {topic_arn}")
        elif error_code == 'AuthorizationError':
            logger.error(f"Not authorized to access SNS topic: {topic_arn}")
        else:
            logger.error(f"Error validating SNS topic: {str(e)}")

        return False
