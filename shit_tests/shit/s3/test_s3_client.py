"""
Tests for S3Client - S3 connection management and configuration.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from botocore.exceptions import ClientError

from shit.s3.s3_client import S3Client
from shit.s3.s3_config import S3Config


class TestS3Client:
    """Test cases for S3Client."""

    @pytest.fixture
    def test_s3_config(self):
        """Test S3 configuration."""
        return S3Config(
            bucket_name="test-bucket",
            prefix="test-prefix",
            region="us-east-1",
            access_key_id="test-access-key",
            secret_access_key="test-secret-key"
        )

    @pytest.fixture
    def s3_client(self, test_s3_config):
        """S3 client instance for testing."""
        return S3Client(test_s3_config)

    @pytest.mark.asyncio
    async def test_initialization_success(self, s3_client):
        """Test successful S3 client initialization."""
        with patch('shit.s3.s3_client.boto3') as mock_boto3:
            # Mock boto3 client and resource
            mock_client = MagicMock()
            mock_resource = MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_boto3.resource.return_value = mock_resource
            
            # Mock head_bucket call (connection test)
            mock_client.head_bucket = MagicMock()
            
            await s3_client.initialize()
            
            # Verify boto3 client and resource were created
            mock_boto3.client.assert_called_once()
            mock_boto3.resource.assert_called_once()
            assert s3_client._client == mock_client
            assert s3_client._resource == mock_resource

    @pytest.mark.asyncio
    async def test_initialization_with_settings(self):
        """Test S3 client initialization with settings."""
        with patch('shit.s3.s3_client.settings') as mock_settings:
            mock_settings.S3_BUCKET_NAME = "settings-bucket"
            mock_settings.S3_PREFIX = "settings-prefix"
            mock_settings.AWS_REGION = "us-west-2"
            mock_settings.AWS_ACCESS_KEY_ID = "settings-key"
            mock_settings.AWS_SECRET_ACCESS_KEY = "settings-secret"
            
            client = S3Client()  # No config provided, should use settings
            
            with patch('shit.s3.s3_client.boto3') as mock_boto3:
                mock_client = MagicMock()
                mock_resource = MagicMock()
                mock_boto3.client.return_value = mock_client
                mock_boto3.resource.return_value = mock_resource
                mock_client.head_bucket = MagicMock()
                
                await client.initialize()
                
                # Verify settings were used
                assert client.config.bucket_name == "settings-bucket"
                assert client.config.prefix == "settings-prefix"
                assert client.config.region == "us-west-2"

    @pytest.mark.asyncio
    async def test_initialization_connection_error(self, s3_client):
        """Test S3 client initialization with connection error."""
        with patch('shit.s3.s3_client.boto3') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            
            # Mock head_bucket to raise ClientError
            mock_client.head_bucket.side_effect = ClientError(
                error_response={'Error': {'Code': 'NoSuchBucket'}},
                operation_name='HeadBucket'
            )
            
            with pytest.raises(ClientError):
                await s3_client.initialize()

    @pytest.mark.asyncio
    async def test_initialization_credentials_error(self, s3_client):
        """Test S3 client initialization with credentials error."""
        with patch('shit.s3.s3_client.boto3') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            
            # Mock head_bucket to raise credentials error
            mock_client.head_bucket.side_effect = ClientError(
                error_response={'Error': {'Code': 'InvalidAccessKeyId'}},
                operation_name='HeadBucket'
            )
            
            with pytest.raises(ClientError):
                await s3_client.initialize()

    def test_config_property(self, s3_client, test_s3_config):
        """Test config property access."""
        assert s3_client.config == test_s3_config
        assert s3_client.config.bucket_name == test_s3_config.bucket_name

    @pytest.mark.asyncio
    async def test_get_client(self, s3_client):
        """Test getting S3 client."""
        with patch('shit.s3.s3_client.boto3') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.head_bucket = MagicMock()
            
            await s3_client.initialize()
            client = s3_client.get_client()
            
            assert client == mock_client

    @pytest.mark.asyncio
    async def test_get_resource(self, s3_client):
        """Test getting S3 resource."""
        with patch('shit.s3.s3_client.boto3') as mock_boto3:
            mock_resource = MagicMock()
            mock_boto3.resource.return_value = mock_resource
            mock_boto3.client.return_value = MagicMock()
            
            await s3_client.initialize()
            resource = s3_client.get_resource()
            
            assert resource == mock_resource

    @pytest.mark.asyncio
    async def test_get_client_before_initialization(self, s3_client):
        """Test getting client before initialization."""
        with pytest.raises(RuntimeError, match="S3 client not initialized"):
            s3_client.get_client()

    @pytest.mark.asyncio
    async def test_get_resource_before_initialization(self, s3_client):
        """Test getting resource before initialization."""
        with pytest.raises(RuntimeError, match="S3 resource not initialized"):
            s3_client.get_resource()

    @pytest.mark.asyncio
    async def test_cleanup(self, s3_client):
        """Test S3 client cleanup."""
        with patch('shit.s3.s3_client.boto3') as mock_boto3:
            mock_client = MagicMock()
            mock_resource = MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_boto3.resource.return_value = mock_resource
            mock_client.head_bucket = MagicMock()
            
            await s3_client.initialize()
            await s3_client.cleanup()
            
            # Verify cleanup (if any cleanup methods exist)
            # Note: boto3 clients don't typically need explicit cleanup

    @pytest.mark.asyncio
    async def test_initialization_with_custom_config(self):
        """Test initialization with custom configuration."""
        custom_config = S3Config(
            bucket_name="custom-bucket",
            prefix="custom-prefix",
            region="eu-west-1",
            access_key_id="custom-key",
            secret_access_key="custom-secret",
            timeout_seconds=60,
            max_retries=5
        )
        
        client = S3Client(custom_config)
        
        with patch('shit.s3.s3_client.boto3') as mock_boto3:
            mock_client = MagicMock()
            mock_resource = MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_boto3.resource.return_value = mock_resource
            mock_client.head_bucket = MagicMock()
            
            await client.initialize()
            
            # Verify custom config was used
            assert client.config.bucket_name == "custom-bucket"
            assert client.config.region == "eu-west-1"
            assert client.config.timeout_seconds == 60
            assert client.config.max_retries == 5

    @pytest.mark.asyncio
    async def test_initialization_retry_logic(self, s3_client):
        """Test initialization retry logic."""
        with patch('shit.s3.s3_client.boto3') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            
            # Mock head_bucket to fail first, then succeed
            call_count = 0
            def mock_head_bucket(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ClientError(
                        error_response={'Error': {'Code': 'ServiceUnavailable'}},
                        operation_name='HeadBucket'
                    )
                return {}
            
            mock_client.head_bucket.side_effect = mock_head_bucket
            
            # This should raise the error (no retry logic implemented yet)
            with pytest.raises(ClientError):
                await s3_client.initialize()

    @pytest.mark.asyncio
    async def test_initialization_timeout(self, s3_client):
        """Test initialization timeout handling."""
        with patch('shit.s3.s3_client.boto3') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            
            # Mock head_bucket to timeout
            mock_client.head_bucket.side_effect = ClientError(
                error_response={'Error': {'Code': 'RequestTimeout'}},
                operation_name='HeadBucket'
            )
            
            with pytest.raises(ClientError):
                await s3_client.initialize()

    def test_config_validation(self, s3_client):
        """Test configuration validation."""
        # Test with valid config
        assert s3_client.config.bucket_name == "test-bucket"
        assert s3_client.config.region == "us-east-1"
        
        # Test config properties
        assert s3_client.config.access_key_id == "test-access-key"
        assert s3_client.config.secret_access_key == "test-secret-key"

    @pytest.mark.asyncio
    async def test_initialization_with_none_config(self):
        """Test initialization with None config (should use settings)."""
        with patch('shit.s3.s3_client.settings') as mock_settings:
            mock_settings.S3_BUCKET_NAME = "default-bucket"
            mock_settings.S3_PREFIX = "default-prefix"
            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.AWS_ACCESS_KEY_ID = "default-key"
            mock_settings.AWS_SECRET_ACCESS_KEY = "default-secret"
            
            client = S3Client(None)
            
            with patch('shit.s3.s3_client.boto3') as mock_boto3:
                mock_client = MagicMock()
                mock_resource = MagicMock()
                mock_boto3.client.return_value = mock_client
                mock_boto3.resource.return_value = mock_resource
                mock_client.head_bucket = MagicMock()
                
                await client.initialize()
                
                # Verify default settings were used
                assert client.config.bucket_name == "default-bucket"

    @pytest.mark.asyncio
    async def test_initialization_boto3_error(self, s3_client):
        """Test initialization with boto3 import error."""
        with patch('shit.s3.s3_client.boto3', side_effect=ImportError("boto3 not available")):
            with pytest.raises(ImportError, match="boto3 not available"):
                await s3_client.initialize()

    def test_string_representation(self, s3_client):
        """Test string representation of S3 client."""
        str_repr = str(s3_client)
        assert "S3Client" in str_repr
        assert "test-bucket" in str_repr

    def test_equality_comparison(self, test_s3_config):
        """Test equality comparison between S3 clients."""
        client1 = S3Client(test_s3_config)
        client2 = S3Client(test_s3_config)
        
        # Note: This would require implementing __eq__ method in S3Client
        # For now, just test that they have the same config
        assert client1.config == client2.config
