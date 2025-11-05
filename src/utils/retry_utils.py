"""
Retry Utilities Module
=====================

Implements exponential backoff with jitter for handling AWS API throttling
and transient errors.
"""

import time
import random
import logging
from functools import wraps
from typing import Callable, Any, Tuple, Type
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Retryable error codes
RETRYABLE_ERROR_CODES = {
    'ThrottlingException',
    'Throttling',
    'TooManyRequestsException',
    'ProvisionedThroughputExceededException',
    'RequestLimitExceeded',
    'ServiceUnavailable',
    'InternalError',
    'RequestTimeout',
    'PriorRequestNotComplete'
}

# HTTP status codes that are retryable
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is retryable.

    Args:
        error: Exception to check

    Returns:
        True if error should be retried, False otherwise
    """
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        http_code = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)

        # Check if error code is retryable
        if error_code in RETRYABLE_ERROR_CODES:
            return True

        # Check if HTTP status code is retryable
        if http_code in RETRYABLE_HTTP_CODES:
            return True

    # Check for connection errors (always retryable)
    if any(err_type in str(type(error).__name__) for err_type in
           ['ConnectionError', 'Timeout', 'ReadTimeout', 'ConnectTimeout']):
        return True

    return False


def calculate_backoff_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 32.0) -> float:
    """
    Calculate exponential backoff delay with jitter.

    Uses full jitter strategy: delay = random(0, min(max_delay, base * 2^attempt))

    Args:
        attempt: Current retry attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds
    """
    # Calculate exponential delay
    exponential_delay = base_delay * (2 ** attempt)

    # Cap at max_delay
    capped_delay = min(exponential_delay, max_delay)

    # Add full jitter
    jittered_delay = random.uniform(0, capped_delay)

    return jittered_delay


def retry_with_exponential_backoff(
    max_retries: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 32.0,
    exceptions: Tuple[Type[Exception], ...] = (ClientError,)
) -> Callable:
    """
    Decorator to retry a function with exponential backoff and jitter.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    # Check if error is retryable
                    if not is_retryable_error(e):
                        logger.debug(f"{func.__name__}: Non-retryable error, raising immediately")
                        raise

                    # Don't retry if this was the last attempt
                    if attempt == max_retries:
                        logger.warning(f"{func.__name__}: Max retries ({max_retries}) reached")
                        break

                    # Calculate backoff delay
                    delay = calculate_backoff_delay(attempt, base_delay, max_delay)

                    logger.warning(
                        f"{func.__name__}: Attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}. "
                        f"Retrying in {delay:.2f}s"
                    )

                    # Wait before retrying
                    time.sleep(delay)

            # If we get here, all retries failed
            logger.error(f"{func.__name__}: All retry attempts failed")
            raise last_exception

        return wrapper
    return decorator


class RetryStrategy:
    """
    Configurable retry strategy for fine-grained control.
    """

    def __init__(
        self,
        max_retries: int = 4,
        base_delay: float = 1.0,
        max_delay: float = 32.0,
        exceptions: Tuple[Type[Exception], ...] = (ClientError,)
    ):
        """
        Initialize retry strategy.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            exceptions: Tuple of exception types to catch
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exceptions = exceptions

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)

            except self.exceptions as e:
                last_exception = e

                if not is_retryable_error(e) or attempt == self.max_retries:
                    raise

                delay = calculate_backoff_delay(attempt, self.base_delay, self.max_delay)

                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries + 1} failed. "
                    f"Retrying in {delay:.2f}s"
                )

                time.sleep(delay)

        raise last_exception


def batch_with_retry(
    items: list,
    batch_size: int,
    process_func: Callable,
    max_retries: int = 3
) -> Tuple[list, list]:
    """
    Process items in batches with retry logic.

    Args:
        items: List of items to process
        batch_size: Size of each batch
        process_func: Function to process each batch
        max_retries: Maximum retries per batch

    Returns:
        Tuple of (successful_items, failed_items)
    """
    successful = []
    failed = []

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]

        retry_strategy = RetryStrategy(max_retries=max_retries)

        try:
            result = retry_strategy.execute(process_func, batch)
            successful.extend(batch)

        except Exception as e:
            logger.error(f"Batch processing failed after {max_retries} retries: {str(e)}")
            failed.extend(batch)

    return successful, failed
