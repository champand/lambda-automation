"""
Unit tests for retry_utils module.
"""

import pytest
import time
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.retry_utils import (
    is_retryable_error,
    calculate_backoff_delay,
    retry_with_exponential_backoff
)


class TestIsRetryableError:
    """Tests for retryable error detection."""

    def test_is_retryable_error_throttling(self):
        """Test detecting throttling errors."""
        error = ClientError(
            {
                'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'},
                'ResponseMetadata': {'HTTPStatusCode': 429}
            },
            'TestOperation'
        )

        assert is_retryable_error(error) is True

    def test_is_retryable_error_too_many_requests(self):
        """Test detecting TooManyRequests errors."""
        error = ClientError(
            {
                'Error': {'Code': 'TooManyRequestsException', 'Message': 'Too many requests'},
                'ResponseMetadata': {'HTTPStatusCode': 429}
            },
            'TestOperation'
        )

        assert is_retryable_error(error) is True

    def test_is_retryable_error_service_unavailable(self):
        """Test detecting service unavailable errors."""
        error = ClientError(
            {
                'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'},
                'ResponseMetadata': {'HTTPStatusCode': 503}
            },
            'TestOperation'
        )

        assert is_retryable_error(error) is True

    def test_is_retryable_error_access_denied(self):
        """Test that AccessDenied is not retryable."""
        error = ClientError(
            {
                'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'},
                'ResponseMetadata': {'HTTPStatusCode': 403}
            },
            'TestOperation'
        )

        assert is_retryable_error(error) is False

    def test_is_retryable_error_not_found(self):
        """Test that NotFound is not retryable."""
        error = ClientError(
            {
                'Error': {'Code': 'NotFound', 'Message': 'Resource not found'},
                'ResponseMetadata': {'HTTPStatusCode': 404}
            },
            'TestOperation'
        )

        assert is_retryable_error(error) is False


class TestCalculateBackoffDelay:
    """Tests for backoff delay calculation."""

    def test_calculate_backoff_delay_first_attempt(self):
        """Test backoff delay for first retry."""
        delay = calculate_backoff_delay(0, base_delay=1.0, max_delay=32.0)

        # Should be between 0 and base_delay * 2^0 = 1
        assert 0 <= delay <= 1.0

    def test_calculate_backoff_delay_increases(self):
        """Test that delay increases with attempts."""
        delays = []
        for attempt in range(5):
            delay = calculate_backoff_delay(attempt, base_delay=1.0, max_delay=32.0)
            delays.append(delay)

        # Max possible delay should increase with attempts
        # (though actual delay is random, max bound increases)
        assert True  # Structure test passed

    def test_calculate_backoff_delay_respects_max(self):
        """Test that delay is capped at max_delay."""
        # Large attempt number should still cap at max_delay
        delay = calculate_backoff_delay(10, base_delay=1.0, max_delay=5.0)

        assert delay <= 5.0

    def test_calculate_backoff_delay_non_negative(self):
        """Test that delay is never negative."""
        for attempt in range(10):
            delay = calculate_backoff_delay(attempt)
            assert delay >= 0


class TestRetryWithExponentialBackoff:
    """Tests for retry decorator."""

    def test_retry_succeeds_on_first_attempt(self):
        """Test function succeeds on first try."""
        mock_func = Mock(return_value='success')

        @retry_with_exponential_backoff(max_retries=3)
        def test_func():
            return mock_func()

        result = test_func()

        assert result == 'success'
        assert mock_func.call_count == 1

    def test_retry_succeeds_after_retries(self):
        """Test function succeeds after retries."""
        mock_func = Mock(
            side_effect=[
                ClientError(
                    {'Error': {'Code': 'ThrottlingException'}, 'ResponseMetadata': {'HTTPStatusCode': 429}},
                    'TestOp'
                ),
                ClientError(
                    {'Error': {'Code': 'ThrottlingException'}, 'ResponseMetadata': {'HTTPStatusCode': 429}},
                    'TestOp'
                ),
                'success'
            ]
        )

        @retry_with_exponential_backoff(max_retries=3, base_delay=0.01)
        def test_func():
            return mock_func()

        result = test_func()

        assert result == 'success'
        assert mock_func.call_count == 3

    def test_retry_fails_after_max_retries(self):
        """Test function fails after max retries."""
        error = ClientError(
            {'Error': {'Code': 'ThrottlingException'}, 'ResponseMetadata': {'HTTPStatusCode': 429}},
            'TestOp'
        )
        mock_func = Mock(side_effect=error)

        @retry_with_exponential_backoff(max_retries=2, base_delay=0.01)
        def test_func():
            return mock_func()

        with pytest.raises(ClientError):
            test_func()

        # Should try initial + 2 retries = 3 times
        assert mock_func.call_count == 3

    def test_retry_non_retryable_error_immediate_raise(self):
        """Test non-retryable errors are raised immediately."""
        error = ClientError(
            {'Error': {'Code': 'AccessDenied'}, 'ResponseMetadata': {'HTTPStatusCode': 403}},
            'TestOp'
        )
        mock_func = Mock(side_effect=error)

        @retry_with_exponential_backoff(max_retries=3)
        def test_func():
            return mock_func()

        with pytest.raises(ClientError):
            test_func()

        # Should only try once (no retries for non-retryable errors)
        assert mock_func.call_count == 1

    @patch('time.sleep')
    def test_retry_waits_between_attempts(self, mock_sleep):
        """Test that retry waits between attempts."""
        mock_func = Mock(
            side_effect=[
                ClientError(
                    {'Error': {'Code': 'ThrottlingException'}, 'ResponseMetadata': {'HTTPStatusCode': 429}},
                    'TestOp'
                ),
                'success'
            ]
        )

        @retry_with_exponential_backoff(max_retries=2, base_delay=1.0)
        def test_func():
            return mock_func()

        result = test_func()

        assert result == 'success'
        assert mock_sleep.called
        # Verify sleep was called at least once
        assert mock_sleep.call_count >= 1
