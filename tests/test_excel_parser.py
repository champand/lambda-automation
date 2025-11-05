"""
Unit tests for excel_parser module.
"""

import pytest
import os
from openpyxl import Workbook

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.excel_parser import (
    normalize_column_names,
    clean_cell_value,
    validate_row_data,
    extract_tags_from_row,
    get_resource_info
)


class TestNormalizeColumnNames:
    """Tests for column name normalization."""

    def test_normalize_column_names_standard(self):
        """Test normalizing standard column names."""
        headers = ('arn', 'accountId', 'resourceType', 'resourceId', 'awsRegion')
        result = normalize_column_names(headers)

        assert result == ['arn', 'accountId', 'resourceType', 'resourceId', 'awsRegion']

    def test_normalize_column_names_with_aliases(self):
        """Test normalizing column names with known aliases."""
        headers = ('ARN', 'account_id', 'resource_type', 'ResourceId', 'Region')
        result = normalize_column_names(headers)

        assert result == ['arn', 'accountId', 'resourceType', 'resourceId', 'awsRegion']

    def test_normalize_column_names_with_empty(self):
        """Test normalizing with empty cells."""
        headers = ('arn', None, '', 'accountId')
        result = normalize_column_names(headers)

        assert result == ['arn', '', '', 'accountId']

    def test_normalize_column_names_custom_tags(self):
        """Test normalizing custom tag columns."""
        headers = ('arn', 'pl:cost-allocation:environment', 'tag:owner')
        result = normalize_column_names(headers)

        assert result == ['arn', 'pl:cost-allocation:environment', 'tag:owner']


class TestCleanCellValue:
    """Tests for cell value cleaning."""

    def test_clean_cell_value_string(self):
        """Test cleaning string values."""
        assert clean_cell_value('  test  ') == 'test'
        assert clean_cell_value('value') == 'value'

    def test_clean_cell_value_none(self):
        """Test cleaning None values."""
        assert clean_cell_value(None) is None
        assert clean_cell_value('none') is None
        assert clean_cell_value('NULL') is None
        assert clean_cell_value('n/a') is None

    def test_clean_cell_value_numbers(self):
        """Test cleaning numeric values."""
        assert clean_cell_value(123) == 123
        assert clean_cell_value(123.0) == 123
        assert clean_cell_value(123.45) == 123.45

    def test_clean_cell_value_boolean(self):
        """Test cleaning boolean values."""
        assert clean_cell_value(True) is True
        assert clean_cell_value(False) is False


class TestValidateRowData:
    """Tests for row data validation."""

    def test_validate_row_data_with_arn(self):
        """Test validation with ARN present."""
        row_data = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
            'pl:cost-allocation:environment': 'prod'
        }

        result = validate_row_data(row_data, 'EC2')

        assert result['valid'] is True

    def test_validate_row_data_without_arn(self):
        """Test validation without ARN but with required fields."""
        row_data = {
            'accountId': '123456789012',
            'resourceType': 'EC2',
            'resourceId': 'i-12345',
            'awsRegion': 'us-east-1',
            'pl:cost-allocation:environment': 'prod'
        }

        result = validate_row_data(row_data, 'EC2')

        assert result['valid'] is True

    def test_validate_row_data_missing_account_id(self):
        """Test validation fails without account ID."""
        row_data = {
            'resourceId': 'i-12345',
            'pl:cost-allocation:environment': 'prod'
        }

        result = validate_row_data(row_data, 'EC2')

        assert result['valid'] is False
        assert 'accountId' in result['error'].lower()

    def test_validate_row_data_invalid_account_id(self):
        """Test validation fails with invalid account ID."""
        row_data = {
            'accountId': 'invalid',
            'resourceId': 'i-12345',
            'pl:cost-allocation:environment': 'prod'
        }

        result = validate_row_data(row_data, 'EC2')

        assert result['valid'] is False
        assert 'account id' in result['error'].lower()

    def test_validate_row_data_missing_resource_id(self):
        """Test validation fails without resource ID."""
        row_data = {
            'accountId': '123456789012',
            'pl:cost-allocation:environment': 'prod'
        }

        result = validate_row_data(row_data, 'EC2')

        assert result['valid'] is False
        assert 'resourceId' in result['error']

    def test_validate_row_data_no_tags(self):
        """Test validation fails without any tags."""
        row_data = {
            'accountId': '123456789012',
            'resourceId': 'i-12345'
        }

        result = validate_row_data(row_data, 'EC2')

        assert result['valid'] is False
        assert 'tag' in result['error'].lower()


class TestExtractTagsFromRow:
    """Tests for tag extraction."""

    def test_extract_tags_from_row_basic(self):
        """Test basic tag extraction."""
        row_data = {
            'accountId': '123456789012',
            'resourceId': 'i-12345',
            'pl:cost-allocation:environment': 'production',
            'pl:cost-allocation:team': 'engineering'
        }

        tags = extract_tags_from_row(row_data)

        assert tags == {
            'pl:cost-allocation:environment': 'production',
            'pl:cost-allocation:team': 'engineering'
        }

    def test_extract_tags_from_row_exclude_resource_fields(self):
        """Test that resource identification fields are excluded."""
        row_data = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
            'accountId': '123456789012',
            'resourceId': 'i-12345',
            'awsRegion': 'us-east-1',
            'pl:cost-allocation:environment': 'production'
        }

        tags = extract_tags_from_row(row_data)

        assert 'arn' not in tags
        assert 'accountId' not in tags
        assert 'resourceId' not in tags
        assert 'awsRegion' not in tags
        assert 'pl:cost-allocation:environment' in tags

    def test_extract_tags_from_row_exclude_empty(self):
        """Test that empty tag values are excluded."""
        row_data = {
            'accountId': '123456789012',
            'pl:cost-allocation:environment': 'production',
            'pl:cost-allocation:team': '',
            'pl:cost-allocation:project': None
        }

        tags = extract_tags_from_row(row_data)

        assert len(tags) == 1
        assert 'pl:cost-allocation:environment' in tags


class TestGetResourceInfo:
    """Tests for resource info extraction."""

    def test_get_resource_info_complete(self):
        """Test extracting complete resource information."""
        row_data = {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
            'accountId': '123456789012',
            'resourceType': 'EC2',
            'resourceId': 'i-12345',
            'awsRegion': 'us-east-1',
            '_sheet_name': 'EC2'
        }

        info = get_resource_info(row_data)

        assert info['arn'] == 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345'
        assert info['accountId'] == '123456789012'
        assert info['resourceType'] == 'EC2'
        assert info['resourceId'] == 'i-12345'
        assert info['awsRegion'] == 'us-east-1'

    def test_get_resource_info_defaults_to_sheet_name(self):
        """Test that resource type defaults to sheet name."""
        row_data = {
            'accountId': '123456789012',
            'resourceId': 'i-12345',
            '_sheet_name': 'EC2'
        }

        info = get_resource_info(row_data)

        assert info['resourceType'] == 'EC2'

    def test_get_resource_info_numeric_account_id(self):
        """Test handling numeric account ID."""
        row_data = {
            'accountId': 123456789012,
            'resourceId': 'i-12345',
            '_sheet_name': 'EC2'
        }

        info = get_resource_info(row_data)

        assert info['accountId'] == '123456789012'
        assert isinstance(info['accountId'], str)
