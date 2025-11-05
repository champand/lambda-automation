"""
AWS Lambda Function: Automated Resource Tagging from Excel Input
================================================================

This Lambda function automates the tagging of AWS resources across multiple
member accounts using an input Excel file stored in S3.

Main Features:
- Reads multi-sheet Excel files from S3
- Assumes roles in member accounts for cross-account tagging
- Supports 20+ AWS resource types
- Generates comprehensive tagging reports
- Sends SNS notifications with presigned download links
- Implements exponential backoff for throttling
- Provides detailed logging and error handling

Author: AWS Cloud Architect Team
Version: 1.0.0
Python: 3.12+
"""

import os
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# Import helper modules
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.s3_operations import (
    download_excel_from_s3,
    upload_report_to_s3,
    generate_presigned_url
)
from utils.excel_parser import (
    parse_excel_sheets,
    validate_row_data
)
from utils.sts_operations import (
    assume_member_role,
    get_session_clients
)
from utils.tagging_service import (
    apply_tags_to_resource,
    batch_tag_resources
)
from utils.report_generator import (
    initialize_report,
    add_report_row,
    finalize_report,
    generate_summary_stats
)
from utils.sns_operations import (
    send_tagging_notification
)
from utils.config_validator import (
    validate_environment_config,
    parse_account_ids
)

# Configure logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function for automated resource tagging.

    This function orchestrates the entire tagging workflow:
    1. Validates environment configuration
    2. Downloads and parses input Excel file from S3
    3. Assumes roles in member accounts
    4. Applies tags to resources across multiple services
    5. Generates comprehensive report
    6. Uploads report to S3 and generates presigned URL
    7. Sends SNS notification with summary

    Args:
        event: Lambda event object (can contain manual overrides)
        context: Lambda context object

    Returns:
        Dict containing execution status, report location, and summary stats

    Raises:
        Exception: Any unhandled exceptions are logged and re-raised
    """
    # Generate unique execution ID for tracing
    execution_id = f"exec-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    logger.info(f"Starting tagging execution: {execution_id}")

    try:
        # Step 1: Validate environment configuration
        logger.info("Step 1/7: Validating environment configuration")
        config = validate_environment_config()
        logger.info(f"Configuration validated. Target accounts: {config['account_ids']}")

        # Check if we have any accounts to process
        if not config['account_ids']:
            logger.warning("No AWS_ACCOUNT_IDS configured. Exiting without processing.")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'SKIPPED',
                    'message': 'No account IDs configured for processing',
                    'execution_id': execution_id
                })
            }

        # Step 2: Download and parse Excel file from S3
        logger.info(f"Step 2/7: Downloading Excel file from S3: s3://{config['s3_bucket']}/{config['input_file']}")
        excel_file_path = download_excel_from_s3(
            bucket=config['s3_bucket'],
            key=config['input_file'],
            region=config['region']
        )
        logger.info(f"Excel file downloaded successfully to: {excel_file_path}")

        # Step 3: Parse all sheets from Excel file
        logger.info("Step 3/7: Parsing Excel sheets")
        sheets_data = parse_excel_sheets(excel_file_path)

        total_rows = sum(len(rows) for rows in sheets_data.values())
        logger.info(f"Parsed {len(sheets_data)} sheets with {total_rows} total rows")

        # Initialize report structure
        report_data = initialize_report()

        # Step 4: Process each sheet and apply tags
        logger.info("Step 4/7: Processing resources and applying tags")

        processed_count = 0
        success_count = 0
        failed_count = 0
        skipped_count = 0
        partial_count = 0

        for sheet_name, rows in sheets_data.items():
            logger.info(f"Processing sheet: {sheet_name} ({len(rows)} rows)")

            for row_idx, row_data in enumerate(rows, start=2):  # Row 2 because row 1 is header
                processed_count += 1

                try:
                    # Validate row data
                    validation_result = validate_row_data(row_data, sheet_name)

                    if not validation_result['valid']:
                        logger.warning(f"Row {row_idx} validation failed: {validation_result['error']}")
                        add_report_row(
                            report_data,
                            sheet_name=sheet_name,
                            row_number=row_idx,
                            row_data=row_data,
                            status='SKIPPED',
                            error_message=validation_result['error'],
                            tags_applied=[]
                        )
                        skipped_count += 1
                        continue

                    # Extract account ID from row
                    account_id = row_data.get('accountId') or row_data.get('account_id') or row_data.get('AccountId')

                    # Check if account is in our target list
                    if account_id not in config['account_ids']:
                        logger.debug(f"Row {row_idx}: Account {account_id} not in target list, skipping")
                        add_report_row(
                            report_data,
                            sheet_name=sheet_name,
                            row_number=row_idx,
                            row_data=row_data,
                            status='SKIPPED',
                            error_message=f"Account {account_id} not in target account list",
                            tags_applied=[]
                        )
                        skipped_count += 1
                        continue

                    # Assume role in member account
                    logger.debug(f"Row {row_idx}: Assuming role in account {account_id}")

                    try:
                        session_credentials = assume_member_role(
                            account_id=account_id,
                            role_name=config['member_role_name'],
                            session_name=f"tagging-{execution_id}",
                            region=config['region']
                        )
                    except Exception as assume_error:
                        logger.error(f"Row {row_idx}: Failed to assume role in account {account_id}: {str(assume_error)}")
                        add_report_row(
                            report_data,
                            sheet_name=sheet_name,
                            row_number=row_idx,
                            row_data=row_data,
                            status='FAILED',
                            error_message=f"Failed to assume role: {str(assume_error)}",
                            tags_applied=[]
                        )
                        failed_count += 1
                        continue

                    # Apply tags to resource
                    logger.debug(f"Row {row_idx}: Applying tags to resource")
                    tagging_result = apply_tags_to_resource(
                        row_data=row_data,
                        sheet_name=sheet_name,
                        session_credentials=session_credentials,
                        region=config['region']
                    )

                    # Record result in report
                    add_report_row(
                        report_data,
                        sheet_name=sheet_name,
                        row_number=row_idx,
                        row_data=row_data,
                        status=tagging_result['status'],
                        error_message=tagging_result.get('error_message'),
                        tags_applied=tagging_result.get('tags_applied', [])
                    )

                    # Update counters
                    if tagging_result['status'] == 'SUCCESS':
                        success_count += 1
                    elif tagging_result['status'] == 'PARTIAL':
                        partial_count += 1
                    elif tagging_result['status'] == 'FAILED':
                        failed_count += 1
                    else:
                        skipped_count += 1

                    # Log progress every 10 rows
                    if processed_count % 10 == 0:
                        logger.info(f"Progress: {processed_count}/{total_rows} rows processed")

                except Exception as row_error:
                    logger.error(f"Row {row_idx}: Unexpected error: {str(row_error)}")
                    logger.debug(traceback.format_exc())
                    add_report_row(
                        report_data,
                        sheet_name=sheet_name,
                        row_number=row_idx,
                        row_data=row_data,
                        status='FAILED',
                        error_message=f"Unexpected error: {str(row_error)}",
                        tags_applied=[]
                    )
                    failed_count += 1

        logger.info(f"Step 4 complete. Processed: {processed_count}, Success: {success_count}, "
                   f"Failed: {failed_count}, Partial: {partial_count}, Skipped: {skipped_count}")

        # Step 5: Finalize report and generate summary
        logger.info("Step 5/7: Generating final report")
        report_content = finalize_report(report_data)

        summary_stats = {
            'execution_id': execution_id,
            'total_rows': processed_count,
            'successful': success_count,
            'failed': failed_count,
            'partial': partial_count,
            'skipped': skipped_count,
            'start_time': report_data['metadata']['start_time'],
            'end_time': datetime.now(timezone.utc).isoformat()
        }

        # Step 6: Upload report to S3
        logger.info("Step 6/7: Uploading report to S3")
        report_key = f"{config['report_prefix']}{execution_id}.xlsx"

        upload_report_to_s3(
            report_content=report_content,
            bucket=config['s3_bucket'],
            key=report_key,
            region=config['region']
        )

        logger.info(f"Report uploaded to: s3://{config['s3_bucket']}/{report_key}")

        # Generate presigned URL for report download
        presigned_url = generate_presigned_url(
            bucket=config['s3_bucket'],
            key=report_key,
            expiry=config['presigned_expiry'],
            region=config['region']
        )

        # Step 7: Send SNS notification
        logger.info("Step 7/7: Sending SNS notification")

        notification_result = send_tagging_notification(
            topic_arn=config['sns_topic_arn'],
            summary_stats=summary_stats,
            presigned_url=presigned_url,
            report_location=f"s3://{config['s3_bucket']}/{report_key}",
            region=config['region']
        )

        logger.info(f"SNS notification sent. MessageId: {notification_result.get('MessageId')}")

        # Final success response
        logger.info(f"Tagging execution {execution_id} completed successfully")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'SUCCESS',
                'execution_id': execution_id,
                'summary': summary_stats,
                'report_location': f"s3://{config['s3_bucket']}/{report_key}",
                'presigned_url': presigned_url,
                'message': f"Successfully processed {total_rows} rows"
            }, default=str)
        }

    except Exception as e:
        # Handle any unhandled exceptions
        logger.error(f"Fatal error in lambda_handler: {str(e)}")
        logger.error(traceback.format_exc())

        # Attempt to send error notification
        try:
            config = validate_environment_config()
            error_summary = {
                'execution_id': execution_id,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Send error notification via SNS
            import boto3
            sns_client = boto3.client('sns', region_name=config['region'])
            sns_client.publish(
                TopicArn=config['sns_topic_arn'],
                Subject='❌ AWS Tagging Lambda - Execution Failed',
                Message=f"Execution ID: {execution_id}\n\n"
                       f"Error: {str(e)}\n\n"
                       f"Time: {datetime.now(timezone.utc).isoformat()}\n\n"
                       f"Check CloudWatch Logs for details."
            )
        except Exception as notify_error:
            logger.error(f"Failed to send error notification: {str(notify_error)}")

        # Return error response
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'ERROR',
                'execution_id': execution_id,
                'error': str(e),
                'message': 'Lambda execution failed. Check CloudWatch Logs for details.'
            })
        }
