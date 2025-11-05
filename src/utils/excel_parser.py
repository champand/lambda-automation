"""
Excel Parser Module
==================

Parses multi-sheet Excel files containing resource information and tags.
Handles missing sheets, columns, and validates row data.
"""

import logging
from typing import Dict, List, Any, Optional
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

logger = logging.getLogger(__name__)

# Known sheet names for different AWS resource types
KNOWN_SHEET_NAMES = {
    'EC2', 'EBS', 'NAT', 'S3', 'LB', 'RDS', 'EKS', 'Glue', 'Prometheus',
    'VPC', 'Firewall', 'MSK', 'OpenSearch', 'SageMaker', 'DocDB',
    'GuardDuty', 'SecurityHub', 'ElastiCache', 'RedShift', 'CloudFront'
}

# Common column name variations
COLUMN_ALIASES = {
    'arn': ['arn', 'ARN', 'resource_arn', 'resourceArn', 'ResourceARN'],
    'accountId': ['accountId', 'account_id', 'AccountId', 'account', 'Account', 'aws_account_id'],
    'resourceType': ['resourceType', 'resource_type', 'ResourceType', 'type', 'Type', 'service'],
    'resourceId': ['resourceId', 'resource_id', 'ResourceId', 'id', 'Id', 'resource_identifier'],
    'awsRegion': ['awsRegion', 'aws_region', 'Region', 'region', 'aws_region_name']
}


def parse_excel_sheets(file_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse all sheets from Excel file.

    Args:
        file_path: Path to Excel file

    Returns:
        Dictionary mapping sheet names to list of row dictionaries

    Raises:
        InvalidFileException: If file is not a valid Excel file
        FileNotFoundError: If file doesn't exist
    """
    logger.info(f"Parsing Excel file: {file_path}")

    try:
        workbook = load_workbook(filename=file_path, read_only=True, data_only=True)
    except InvalidFileException as e:
        logger.error(f"Invalid Excel file: {str(e)}")
        raise
    except FileNotFoundError as e:
        logger.error(f"Excel file not found: {str(e)}")
        raise

    sheets_data = {}
    sheet_names = workbook.sheetnames

    logger.info(f"Found {len(sheet_names)} sheets: {sheet_names}")

    for sheet_name in sheet_names:
        # Skip empty or hidden sheets
        if not sheet_name or sheet_name.startswith('_'):
            logger.debug(f"Skipping sheet: {sheet_name}")
            continue

        try:
            sheet_data = parse_sheet(workbook[sheet_name], sheet_name)

            if sheet_data:
                sheets_data[sheet_name] = sheet_data
                logger.info(f"Parsed sheet '{sheet_name}': {len(sheet_data)} rows")
            else:
                logger.warning(f"Sheet '{sheet_name}' is empty or has no valid data")

        except Exception as e:
            logger.error(f"Error parsing sheet '{sheet_name}': {str(e)}")
            # Continue processing other sheets

    workbook.close()

    if not sheets_data:
        logger.warning("No valid data found in any sheet")

    return sheets_data


def parse_sheet(sheet, sheet_name: str) -> List[Dict[str, Any]]:
    """
    Parse a single Excel sheet.

    Args:
        sheet: openpyxl worksheet object
        sheet_name: Name of the sheet

    Returns:
        List of dictionaries, one per row
    """
    rows_data = []

    # Get header row (first row)
    rows = list(sheet.iter_rows(values_only=True))

    if not rows:
        logger.warning(f"Sheet '{sheet_name}' has no rows")
        return []

    header_row = rows[0]

    if not header_row or all(cell is None for cell in header_row):
        logger.warning(f"Sheet '{sheet_name}' has empty header row")
        return []

    # Normalize column names
    normalized_headers = normalize_column_names(header_row)

    logger.debug(f"Sheet '{sheet_name}' columns: {normalized_headers}")

    # Parse data rows
    for row_idx, row in enumerate(rows[1:], start=2):  # Start from row 2
        # Skip completely empty rows
        if not row or all(cell is None or cell == '' for cell in row):
            continue

        # Create row dictionary
        row_dict = {}
        for col_idx, (header, cell_value) in enumerate(zip(normalized_headers, row)):
            if header:  # Skip columns with no header
                # Convert cell value to appropriate type
                row_dict[header] = clean_cell_value(cell_value)

        # Add metadata
        row_dict['_sheet_name'] = sheet_name
        row_dict['_row_number'] = row_idx

        rows_data.append(row_dict)

    return rows_data


def normalize_column_names(header_row: tuple) -> List[str]:
    """
    Normalize column names using known aliases.

    Args:
        header_row: Tuple of header cell values

    Returns:
        List of normalized column names
    """
    normalized = []

    for cell_value in header_row:
        if cell_value is None or cell_value == '':
            normalized.append('')
            continue

        # Convert to string and strip whitespace
        col_name = str(cell_value).strip()

        # Check if column matches any known alias
        normalized_name = col_name
        for standard_name, aliases in COLUMN_ALIASES.items():
            if col_name in aliases:
                normalized_name = standard_name
                break

        normalized.append(normalized_name)

    return normalized


def clean_cell_value(value: Any) -> Any:
    """
    Clean and normalize cell value.

    Args:
        value: Raw cell value

    Returns:
        Cleaned value
    """
    if value is None:
        return None

    # Handle strings
    if isinstance(value, str):
        value = value.strip()
        # Convert common null representations to None
        if value.lower() in ['', 'none', 'null', 'n/a', 'na', '#n/a']:
            return None
        return value

    # Handle numbers
    if isinstance(value, (int, float)):
        # Convert floats that are actually ints
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    # Handle booleans
    if isinstance(value, bool):
        return value

    # For other types, convert to string
    return str(value)


def validate_row_data(row_data: Dict[str, Any], sheet_name: str) -> Dict[str, Any]:
    """
    Validate row data has required fields for resource identification.

    Required: Either 'arn' OR ('accountId' AND 'resourceType' AND 'resourceId')

    Args:
        row_data: Row dictionary
        sheet_name: Name of the sheet

    Returns:
        Dictionary with 'valid' boolean and optional 'error' message
    """
    # Check if ARN is present
    arn = row_data.get('arn')
    if arn and isinstance(arn, str) and arn.startswith('arn:aws:'):
        return {'valid': True}

    # If no ARN, check for alternative identification
    account_id = row_data.get('accountId')
    resource_type = row_data.get('resourceType') or sheet_name
    resource_id = row_data.get('resourceId')
    aws_region = row_data.get('awsRegion')

    # Validate account ID
    if not account_id:
        return {
            'valid': False,
            'error': 'Missing required field: accountId or arn'
        }

    # Convert account ID to string and validate format
    account_id = str(account_id).strip()
    if not account_id.isdigit() or len(account_id) != 12:
        return {
            'valid': False,
            'error': f'Invalid account ID format: {account_id}'
        }

    # Validate resource ID
    if not resource_id:
        return {
            'valid': False,
            'error': 'Missing required field: resourceId (required when arn is not provided)'
        }

    # Resource type defaults to sheet name if not provided
    if not resource_type:
        resource_type = sheet_name

    # Check if at least one tag column exists
    has_tags = any(
        key for key in row_data.keys()
        if key and (
            key.startswith('pl:cost-allocation:') or
            key.startswith('tag:') or
            key.lower() in ['environment', 'cost_center', 'project', 'owner', 'team']
        )
    )

    if not has_tags:
        return {
            'valid': False,
            'error': 'No tag columns found in row'
        }

    return {'valid': True}


def extract_tags_from_row(row_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract tag key-value pairs from row data.

    Args:
        row_data: Row dictionary

    Returns:
        Dictionary of tags to apply
    """
    tags = {}

    for key, value in row_data.items():
        # Skip internal metadata fields
        if key.startswith('_'):
            continue

        # Skip resource identification fields
        if key in ['arn', 'accountId', 'resourceType', 'resourceId', 'awsRegion']:
            continue

        # Check if this looks like a tag column
        if key and (
            key.startswith('pl:cost-allocation:') or
            key.startswith('tag:') or
            key.lower() in ['environment', 'cost_center', 'project', 'owner', 'team']
        ):
            # Skip None or empty values
            if value is None or (isinstance(value, str) and not value.strip()):
                continue

            # Convert to string
            tag_value = str(value).strip()

            # Skip placeholder values
            if tag_value.lower() in ['none', 'null', 'n/a', '']:
                continue

            tags[key] = tag_value

    return tags


def get_resource_info(row_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract resource identification information from row.

    Args:
        row_data: Row dictionary

    Returns:
        Dictionary with resource identification fields
    """
    info = {}

    # ARN (if present)
    if row_data.get('arn'):
        info['arn'] = row_data['arn']

    # Account ID
    if row_data.get('accountId'):
        info['accountId'] = str(row_data['accountId']).strip()

    # Resource type (defaults to sheet name)
    info['resourceType'] = row_data.get('resourceType') or row_data.get('_sheet_name', 'Unknown')

    # Resource ID
    if row_data.get('resourceId'):
        info['resourceId'] = str(row_data['resourceId']).strip()

    # AWS Region
    if row_data.get('awsRegion'):
        info['awsRegion'] = row_data['awsRegion']

    return info
