"""
Unit tests for config_validator module.
"""

import pytest
import os
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.config_validator import (
    validate_environment_config,
    parse_account_ids,
    validate_arn,
    validate_resource_id,
    parse_tags_from_row
)


class TestConfigValidator:
    """Tests for configuration validation functions."""

    @patch.dict(os.environ, {
        'REGION': 'us-east-1',
        'S3_BUCKET': 'test-bucket',
        'TAGGING_INPUT_FILE': 'input.xlsx',
        'TAGGING_REPORT_FILE_PREFIX': 'reports/tagging_',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic',
        'MEMBER_ROLE_NAME': 'TaggingRole',
        'AWS_ACCOUNT_IDS': '123456789012,987654321098',
        'PRESIGNED_URL_EXPIRY': '7200'
    })
    def test_validate_environment_config_success(self):
        """Test successful configuration validation."""
        config = validate_environment_config()

        assert config['region'] == 'us-east-1'
        assert config['s3_bucket'] == 'test-bucket'
        assert config['input_file'] == 'input.xlsx'
        assert config['report_prefix'] == 'reports/tagging_'
        assert config['sns_topic_arn'] == 'arn:aws:sns:us-east-1:123456789012:test-topic'
        assert config['member_role_name'] == 'TaggingRole'
        assert config['account_ids'] == {'123456789012', '987654321098'}
        assert config['presigned_expiry'] == 7200

    @patch.dict(os.environ, {
        'REGION': 'ap-south-1',
        'S3_BUCKET': 'test-bucket',
        'TAGGING_INPUT_FILE': 'input.xlsx',
        'TAGGING_REPORT_FILE_PREFIX': 'report',
        'SNS_TOPIC_ARN': 'arn:aws:sns:ap-south-1:123456789012:topic',
        'MEMBER_ROLE_NAME': 'Role'
    }, clear=True)
    def test_validate_environment_config_default_region(self):
        """Test default region when not specified."""
        config = validate_environment_config()
        assert config['region'] == 'ap-south-1'
        assert config['account_ids'] == set()  # Empty by default

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_environment_config_missing_required(self):
        """Test validation fails with missing required variables."""
        with pytest.raises(ValueError, match="S3_BUCKET"):
            validate_environment_config()

    @patch.dict(os.environ, {
        'S3_BUCKET': 'bucket',
        'TAGGING_INPUT_FILE': 'file.xlsx',
        'TAGGING_REPORT_FILE_PREFIX': 'report',
        'SNS_TOPIC_ARN': 'invalid-arn',
        'MEMBER_ROLE_NAME': 'Role'
    }, clear=True)
    def test_validate_environment_config_invalid_sns_arn(self):
        """Test validation fails with invalid SNS ARN."""
        with pytest.raises(ValueError, match="Invalid SNS_TOPIC_ARN"):
            validate_environment_config()


class TestParseAccountIds:
    """Tests for account ID parsing."""

    def test_parse_account_ids_valid(self):
        """Test parsing valid account IDs."""
        result = parse_account_ids('123456789012,987654321098')
        assert result == {'123456789012', '987654321098'}

    def test_parse_account_ids_with_spaces(self):
        """Test parsing account IDs with spaces."""
        result = parse_account_ids('123456789012 , 987654321098 ')
        assert result == {'123456789012', '987654321098'}

    def test_parse_account_ids_empty(self):
        """Test parsing empty string."""
        result = parse_account_ids('')
        assert result == set()

    def test_parse_account_ids_invalid_format(self):
        """Test parsing invalid account ID format."""
        with pytest.raises(ValueError, match="Invalid AWS account ID"):
            parse_account_ids('123,invalid')

    def test_parse_account_ids_wrong_length(self):
        """Test parsing account ID with wrong length."""
        with pytest.raises(ValueError, match="Invalid AWS account ID"):
            parse_account_ids('12345')


class TestValidateArn:
    """Tests for ARN validation."""

    def test_validate_arn_valid(self):
        """Test validating valid ARN."""
        arn = 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0'
        assert validate_arn(arn) is True

    def test_validate_arn_invalid(self):
        """Test validating invalid ARN."""
        assert validate_arn('not-an-arn') is False
        assert validate_arn('') is False
        assert validate_arn(None) is False


class TestValidateResourceId:
    """Tests for resource ID validation."""

    def test_validate_resource_id_ec2_instance(self):
        """Test validating EC2 instance ID."""
        assert validate_resource_id('i-1234567890abcdef0', 'EC2') is True
        assert validate_resource_id('i-12345', 'EC2') is True

    def test_validate_resource_id_ebs_volume(self):
        """Test validating EBS volume ID."""
        assert validate_resource_id('vol-1234567890abcdef0', 'EBS') is True

    def test_validate_resource_id_s3_bucket(self):
        """Test validating S3 bucket name."""
        assert validate_resource_id('my-bucket-name', 'S3') is True
        assert validate_resource_id('my.bucket.name', 'S3') is True

    def test_validate_resource_id_invalid(self):
        """Test validating invalid resource IDs."""
        assert validate_resource_id('', 'EC2') is False
        assert validate_resource_id('x' * 300, 'EC2') is False


class TestParseTagsFromRow:
    """Tests for tag extraction from row data."""

    def test_parse_tags_from_row_with_cost_allocation_tags(self):
        """Test extracting cost allocation tags."""
        row_data = {
            'accountId': '123456789012',
            'resourceId': 'i-12345',
            'pl:cost-allocation:environment': 'production',
            'pl:cost-allocation:team': 'engineering',
            'pl:cost-allocation:project': 'web-app'
        }

        tags = parse_tags_from_row(row_data)

        assert tags == {
            'pl:cost-allocation:environment': 'production',
            'pl:cost-allocation:team': 'engineering',
            'pl:cost-allocation:project': 'web-app'
        }

    def test_parse_tags_from_row_with_common_tags(self):
        """Test extracting common tag names."""
        row_data = {
            'accountId': '123456789012',
            'resourceId': 'i-12345',
            'environment': 'dev',
            'owner': 'john.doe',
            'team': 'platform'
        }

        tags = parse_tags_from_row(row_data)

        assert 'environment' in tags
        assert 'owner' in tags
        assert 'team' in tags

    def test_parse_tags_from_row_skip_empty_values(self):
        """Test that empty values are skipped."""
        row_data = {
            'accountId': '123456789012',
            'pl:cost-allocation:environment': 'production',
            'pl:cost-allocation:team': '',
            'pl:cost-allocation:project': None,
            'pl:cost-allocation:owner': 'none'
        }

        tags = parse_tags_from_row(row_data)

        assert 'pl:cost-allocation:environment' in tags
        assert 'pl:cost-allocation:team' not in tags
        assert 'pl:cost-allocation:project' not in tags
        assert 'pl:cost-allocation:owner' not in tags

    def test_parse_tags_from_row_no_tags(self):
        """Test row with no tag columns."""
        row_data = {
            'accountId': '123456789012',
            'resourceId': 'i-12345',
            'awsRegion': 'us-east-1'
        }

        tags = parse_tags_from_row(row_data)

        assert tags == {}
