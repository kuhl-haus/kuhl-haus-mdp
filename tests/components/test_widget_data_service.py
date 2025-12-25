import unittest
from typing import Any
from unittest.mock import Mock, patch

from kuhl_haus.mdp.components.widget_data_service import WidgetDataService


class TestWidgetDataService(unittest.TestCase):
    """Unit tests for WidgetDataService."""

    def test_init_with_valid_cache_expect_initialized_service(self):
        """
        Test initialization with a valid cache client.

        Scenario: Initialize WidgetDataService with a mock Redis cache.
        Expected: Service is initialized with empty subscriptions.
        """
        # Arrange
        mock_redis_client = Mock()
        mock_pubsub_client = Mock()
        mock_redis_client.pubsub = Mock()
        mock_redis_client.pubsub.return_value = mock_pubsub_client

        # Act
        service = sut(mock_redis_client, mock_pubsub_client)

        # Assert
        self.assertEqual(service.subscriptions, {})
        self.assertEqual(service.redis_client, mock_redis_client)
        self.assertEqual(service.pubsub_client, mock_pubsub_client)


def sut(redis_client, pubsub_client) -> WidgetDataService:
    """
    System Under Test (SUT) entry point for creating WidgetDataService instances.

    This factory function provides a clean interface for testing and instantiation
    following the functional core pattern.

    Args:
        redis_client: Redis client instance for cache operations.
        pubsub_client: Redis client instance for pubsub operations.

    Returns:
        WidgetDataService: Configured service instance.

    Raises:
        TypeError: If redis_client or pubsub_client are None.
    """
    return WidgetDataService(redis_client, pubsub_client)


if __name__ == "__main__":
    unittest.main()
