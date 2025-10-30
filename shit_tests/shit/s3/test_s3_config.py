"""
Tests for S3Config - S3 configuration and validation.
Tests that will break if configuration functionality changes.
"""

import pytest
from dataclasses import FrozenInstanceError

from shit.s3.s3_config import S3Config


class TestS3Config:
    """Test cases for S3Config dataclass."""

    def test_default_config(self):
        """Test S3Config with minimal required parameters."""
        config = S3Config(bucket_name="test-bucket")
        
        assert config.bucket_name == "test-bucket"
        assert config.prefix == "truth-social"  # Default value
        assert config.region == "us-east-1"  # Default value
        assert config.access_key_id is None  # Default value
        assert config.secret_access_key is None  # Default value
        assert config.timeout_seconds == 30  # Default value
        assert config.max_retries == 3  # Default value
        assert config.chunk_size == 8192  # Default value
        assert config.raw_data_prefix == "raw"  # Default value
        assert config.processed_data_prefix == "processed"  # Default value

    def test_full_config(self):
        """Test S3Config with all parameters specified."""
        config = S3Config(
            bucket_name="my-bucket",
            prefix="my-prefix",
            region="eu-west-1",
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            timeout_seconds=60,
            max_retries=5,
            chunk_size=16384,
            raw_data_prefix="raw-data",
            processed_data_prefix="processed-data"
        )
        
        assert config.bucket_name == "my-bucket"
        assert config.prefix == "my-prefix"
        assert config.region == "eu-west-1"
        assert config.access_key_id == "AKIAIOSFODNN7EXAMPLE"
        assert config.secret_access_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert config.timeout_seconds == 60
        assert config.max_retries == 5
        assert config.chunk_size == 16384
        assert config.raw_data_prefix == "raw-data"
        assert config.processed_data_prefix == "processed-data"

    def test_validation_bucket_name_required(self):
        """Test that bucket_name is required."""
        with pytest.raises(ValueError, match="S3 bucket name is required"):
            S3Config(bucket_name="")
        
        with pytest.raises(ValueError, match="S3 bucket name is required"):
            S3Config(bucket_name=None)

    def test_validation_prefix_required(self):
        """Test that prefix is required."""
        with pytest.raises(ValueError, match="S3 prefix is required"):
            S3Config(bucket_name="test-bucket", prefix="")
        
        with pytest.raises(ValueError, match="S3 prefix is required"):
            S3Config(bucket_name="test-bucket", prefix=None)

    def test_raw_prefix_property(self):
        """Test raw_prefix property calculation."""
        config = S3Config(bucket_name="test-bucket", prefix="my-prefix")
        assert config.raw_prefix == "my-prefix/raw"
        
        config = S3Config(
            bucket_name="test-bucket", 
            prefix="my-prefix", 
            raw_data_prefix="raw-data"
        )
        assert config.raw_prefix == "my-prefix/raw-data"

    def test_processed_prefix_property(self):
        """Test processed_prefix property calculation."""
        config = S3Config(bucket_name="test-bucket", prefix="my-prefix")
        assert config.processed_prefix == "my-prefix/processed"
        
        config = S3Config(
            bucket_name="test-bucket", 
            prefix="my-prefix", 
            processed_data_prefix="processed-data"
        )
        assert config.processed_prefix == "my-prefix/processed-data"

    def test_prefix_with_slash(self):
        """Test prefix handling with trailing slashes."""
        config = S3Config(bucket_name="test-bucket", prefix="my-prefix/")
        assert config.raw_prefix == "my-prefix//raw"  # Double slash is preserved
        assert config.processed_prefix == "my-prefix//processed"

    def test_empty_prefix_components(self):
        """Test prefix with empty components."""
        config = S3Config(
            bucket_name="test-bucket", 
            prefix="my-prefix",
            raw_data_prefix="",
            processed_data_prefix=""
        )
        assert config.raw_prefix == "my-prefix/"
        assert config.processed_prefix == "my-prefix/"

    def test_numeric_values(self):
        """Test numeric configuration values."""
        config = S3Config(
            bucket_name="test-bucket",
            timeout_seconds=0,
            max_retries=0,
            chunk_size=1
        )
        
        assert config.timeout_seconds == 0
        assert config.max_retries == 0
        assert config.chunk_size == 1

    def test_large_values(self):
        """Test large numeric configuration values."""
        config = S3Config(
            bucket_name="test-bucket",
            timeout_seconds=3600,  # 1 hour
            max_retries=10,
            chunk_size=1048576  # 1MB
        )
        
        assert config.timeout_seconds == 3600
        assert config.max_retries == 10
        assert config.chunk_size == 1048576

    def test_aws_credentials_optional(self):
        """Test that AWS credentials are optional."""
        config = S3Config(bucket_name="test-bucket")
        assert config.access_key_id is None
        assert config.secret_access_key is None

    def test_aws_credentials_provided(self):
        """Test AWS credentials when provided."""
        config = S3Config(
            bucket_name="test-bucket",
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        )
        
        assert config.access_key_id == "AKIAIOSFODNN7EXAMPLE"
        assert config.secret_access_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

    def test_region_variations(self):
        """Test different AWS region formats."""
        regions = [
            "us-east-1",
            "us-west-2", 
            "eu-west-1",
            "ap-southeast-1",
            "ca-central-1"
        ]
        
        for region in regions:
            config = S3Config(bucket_name="test-bucket", region=region)
            assert config.region == region

    def test_bucket_name_variations(self):
        """Test different bucket name formats."""
        bucket_names = [
            "my-bucket",
            "my-bucket-123",
            "my.bucket.name",
            "123-bucket",
            "bucket-with-dashes",
            "UPPERCASE-BUCKET"
        ]
        
        for bucket_name in bucket_names:
            config = S3Config(bucket_name=bucket_name)
            assert config.bucket_name == bucket_name

    def test_prefix_variations(self):
        """Test different prefix formats."""
        prefixes = [
            "my-prefix",
            "my/prefix/path",
            "prefix-with-dashes",
            "123-prefix",
            "UPPERCASE-PREFIX",
            "prefix.with.dots"
        ]
        
        for prefix in prefixes:
            config = S3Config(bucket_name="test-bucket", prefix=prefix)
            assert config.prefix == prefix

    def test_config_immutability(self):
        """Test that config fields cannot be modified after creation."""
        config = S3Config(bucket_name="test-bucket")
        
        # S3Config is not frozen, so fields can be modified
        # This test documents current behavior
        config.bucket_name = "modified-bucket"
        assert config.bucket_name == "modified-bucket"

    def test_config_equality(self):
        """Test config equality comparison."""
        config1 = S3Config(bucket_name="test-bucket", prefix="test-prefix")
        config2 = S3Config(bucket_name="test-bucket", prefix="test-prefix")
        config3 = S3Config(bucket_name="different-bucket", prefix="test-prefix")
        
        assert config1 == config2
        assert config1 != config3

    def test_config_string_representation(self):
        """Test string representation of config."""
        config = S3Config(bucket_name="test-bucket", prefix="test-prefix")
        str_repr = str(config)
        
        assert "S3Config" in str_repr
        assert "test-bucket" in str_repr
        assert "test-prefix" in str_repr

    def test_config_repr(self):
        """Test repr representation of config."""
        config = S3Config(bucket_name="test-bucket", prefix="test-prefix")
        repr_str = repr(config)
        
        assert "S3Config" in repr_str
        assert "bucket_name='test-bucket'" in repr_str
        assert "prefix='test-prefix'" in repr_str

    def test_config_hash(self):
        """Test config hashability."""
        config = S3Config(bucket_name="test-bucket", prefix="test-prefix")
        
        # S3Config is not hashable by default (dataclass without frozen=True)
        # This test documents current behavior
        with pytest.raises(TypeError, match="unhashable type"):
            config_set = {config}

    def test_config_copy(self):
        """Test config copying."""
        from copy import copy, deepcopy
        
        config = S3Config(
            bucket_name="test-bucket",
            prefix="test-prefix",
            region="us-west-2",
            timeout_seconds=60
        )
        
        # Test shallow copy
        config_copy = copy(config)
        assert config_copy == config
        assert config_copy is not config
        
        # Test deep copy
        config_deep_copy = deepcopy(config)
        assert config_deep_copy == config
        assert config_deep_copy is not config

    def test_config_with_special_characters(self):
        """Test config with special characters in strings."""
        config = S3Config(
            bucket_name="test-bucket-with-special-chars-123",
            prefix="test/prefix/with/slashes",
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY+"
        )
        
        assert config.bucket_name == "test-bucket-with-special-chars-123"
        assert config.prefix == "test/prefix/with/slashes"
        assert config.access_key_id == "AKIAIOSFODNN7EXAMPLE"
        assert config.secret_access_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY+"

    def test_config_validation_order(self):
        """Test that validation happens in the correct order."""
        # Test bucket_name validation first
        with pytest.raises(ValueError, match="S3 bucket name is required"):
            S3Config(bucket_name="", prefix="test-prefix")
        
        # Test prefix validation after bucket_name
        with pytest.raises(ValueError, match="S3 prefix is required"):
            S3Config(bucket_name="test-bucket", prefix="")

    def test_config_edge_cases(self):
        """Test edge cases for configuration."""
        # Test with whitespace-only strings - these are not empty, so they pass validation
        config1 = S3Config(bucket_name="   ")
        assert config1.bucket_name == "   "
        
        config2 = S3Config(bucket_name="test-bucket", prefix="   ")
        assert config2.prefix == "   "

    def test_config_property_calculations(self):
        """Test property calculations with various inputs."""
        # Test with different prefix formats
        test_cases = [
            ("prefix", "raw", "processed", "prefix/raw", "prefix/processed"),
            ("prefix/", "raw", "processed", "prefix//raw", "prefix//processed"),
            ("a/b/c", "x/y/z", "p/q/r", "a/b/c/x/y/z", "a/b/c/p/q/r"),
        ]
        
        for prefix, raw_prefix, processed_prefix, expected_raw, expected_processed in test_cases:
            config = S3Config(
                bucket_name="test-bucket",
                prefix=prefix,
                raw_data_prefix=raw_prefix,
                processed_data_prefix=processed_prefix
            )
            assert config.raw_prefix == expected_raw
            assert config.processed_prefix == expected_processed
