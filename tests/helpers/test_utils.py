import os
from unittest.mock import patch, mock_open

import pytest
from kuhl_haus.mdp.helpers.utils import get_massive_api_key


@pytest.fixture
def mock_env():
    """Fixture to clear environment variables before each test."""
    original_env = os.environ.copy()
    os.environ.clear()
    yield os.environ
    os.environ.clear()
    os.environ.update(original_env)


@patch("os.environ.get")
def test_get_massive_api_key_from_env(mock_get):
    # Arrange
    sut = get_massive_api_key
    mock_get.side_effect = lambda key: "MASSIVE_ENV_KEY" if key == "MASSIVE_API_KEY" else None

    # Act
    result = sut()

    # Assert
    assert result == "MASSIVE_ENV_KEY"


@patch("os.environ.get")
def test_get_massive_api_key_from_polygon_api_key(mock_get):
    # Arrange
    sut = get_massive_api_key
    mock_get.side_effect = lambda key: "POLYGON_ENV_KEY" if key == "POLYGON_API_KEY" else None

    # Act
    result = sut()

    # Assert
    assert result == "POLYGON_ENV_KEY"


@patch("builtins.open", new_callable=mock_open, read_data="FILE_API_KEY")
@patch("os.environ.get")
def test_get_massive_api_key_from_file(mock_get, mock_file):
    # Arrange
    sut = get_massive_api_key
    mock_get.return_value = None  # Both environment variables are unset

    # Act
    result = sut()

    # Assert
    mock_file.assert_called_once_with("/app/massive_api_key.txt", "r")
    assert result == "FILE_API_KEY"


@patch("builtins.open", side_effect=FileNotFoundError)
@patch("os.environ.get")
def test_get_massive_api_key_file_not_found(mock_get, mock_file):
    # Arrange
    sut = get_massive_api_key
    mock_get.return_value = None  # Both environment variables are unset

    # Act & Assert
    with pytest.raises(ValueError, match="MASSIVE_API_KEY environment variable not set"):
        sut()


@patch("builtins.open", new_callable=mock_open, read_data="   KEY_WITH_WHITESPACE   ")
@patch("os.environ.get")
def test_get_massive_api_key_file_key_stripped(mock_get, mock_file):
    # Arrange
    sut = get_massive_api_key
    mock_get.return_value = None  # Both environment variables are unset

    # Act
    result = sut()

    # Assert
    assert result == "KEY_WITH_WHITESPACE".strip()


@patch("os.environ.get")
def test_get_massive_api_key_all_sources_unavailable(mock_get):
    # Arrange
    sut = get_massive_api_key
    mock_get.return_value = None  # No environment variables set

    # Act & Assert
    with pytest.raises(ValueError, match="MASSIVE_API_KEY environment variable not set"):
        sut()
