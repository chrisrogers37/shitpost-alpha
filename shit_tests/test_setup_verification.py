"""
Simple test to verify the test setup is working correctly.
"""

import pytest
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_import_project_modules():
    """Test that we can import project modules."""
    try:
        # Test core imports
        from shit.db.database_config import DatabaseConfig
        from shit.db.database_client import DatabaseClient
        from shit.s3.s3_config import S3Config
        from shit.s3.s3_client import S3Client
        from shit.llm.llm_client import LLMClient
        
        # Test that classes exist
        assert DatabaseConfig is not None
        assert DatabaseClient is not None
        assert S3Config is not None
        assert S3Client is not None
        assert LLMClient is not None
        
        print("✅ All core modules imported successfully")
        
    except ImportError as e:
        pytest.fail(f"Failed to import project modules: {e}")


def test_test_configuration():
    """Test that test configuration is working."""
    # Test that we can create test configurations
    from shit.db.database_config import DatabaseConfig
    from shit.s3.s3_config import S3Config
    
    # Test database config
    db_config = DatabaseConfig(database_url="sqlite+aiosqlite:///./test.db")
    assert db_config.database_url == "sqlite+aiosqlite:///./test.db"
    assert db_config.is_sqlite is True
    
    # Test S3 config
    s3_config = S3Config(
        bucket_name="test-bucket",
        prefix="test-prefix"
    )
    assert s3_config.bucket_name == "test-bucket"
    assert s3_config.prefix == "test-prefix"
    
    print("✅ Test configurations created successfully")


def test_fixtures_available():
    """Test that test fixtures are available."""
    # Test that fixture files exist
    fixtures_dir = Path(__file__).parent / "fixtures"
    assert fixtures_dir.exists()
    
    # Test data files
    sample_shitposts = fixtures_dir / "test_data" / "sample_shitposts.json"
    sample_llm_responses = fixtures_dir / "test_data" / "sample_llm_responses.json"
    
    assert sample_shitposts.exists()
    assert sample_llm_responses.exists()
    
    # Mock response files
    truth_social_mock = fixtures_dir / "mock_responses" / "truth_social_api.json"
    llm_mock = fixtures_dir / "mock_responses" / "llm_responses.json"
    
    assert truth_social_mock.exists()
    assert llm_mock.exists()
    
    print("✅ Test fixtures are available")


def test_pytest_configuration():
    """Test that pytest configuration is working."""
    # Test that pytest.ini exists
    pytest_ini = Path(__file__).parent / "pytest.ini"
    assert pytest_ini.exists()
    
    # Test that conftest.py exists
    conftest = Path(__file__).parent / "conftest.py"
    assert conftest.exists()
    
    print("✅ Pytest configuration is available")


def test_test_runner():
    """Test that test runner script exists and is executable."""
    test_runner = Path(__file__).parent / "run_tests.py"
    assert test_runner.exists()
    
    # Check if it's executable (on Unix systems)
    if os.name != 'nt':  # Not Windows
        assert os.access(test_runner, os.X_OK)
    
    print("✅ Test runner script is available")


def test_directory_structure():
    """Test that the test directory structure is correct."""
    test_dir = Path(__file__).parent
    
    # Test main directories
    expected_dirs = [
        "shit",
        "shitvault", 
        "shitposts",
        "shitpost_ai",
        "integration",
        "fixtures"
    ]
    
    for dir_name in expected_dirs:
        dir_path = test_dir / dir_name
        assert dir_path.exists(), f"Directory {dir_name} does not exist"
        assert dir_path.is_dir(), f"{dir_name} is not a directory"
    
    # Test shit subdirectories
    shit_dirs = ["config", "db", "llm", "s3", "utils"]
    for dir_name in shit_dirs:
        dir_path = test_dir / "shit" / dir_name
        assert dir_path.exists(), f"Directory shit/{dir_name} does not exist"
    
    print("✅ Test directory structure is correct")


def test_sample_data_loading():
    """Test that sample data can be loaded."""
    import json
    
    # Load sample shitposts
    fixtures_dir = Path(__file__).parent / "fixtures"
    sample_shitposts_file = fixtures_dir / "test_data" / "sample_shitposts.json"
    
    with open(sample_shitposts_file, 'r') as f:
        sample_shitposts = json.load(f)
    
    assert isinstance(sample_shitposts, list)
    assert len(sample_shitposts) > 0
    
    # Verify structure of first post
    first_post = sample_shitposts[0]
    required_fields = ["shitpost_id", "post_timestamp", "content", "author", "engagement"]
    for field in required_fields:
        assert field in first_post, f"Missing field: {field}"
    
    print("✅ Sample data can be loaded")


def test_mock_data_loading():
    """Test that mock data can be loaded."""
    import json
    
    # Load mock responses
    fixtures_dir = Path(__file__).parent / "fixtures"
    mock_responses_file = fixtures_dir / "mock_responses" / "truth_social_api.json"
    
    with open(mock_responses_file, 'r') as f:
        mock_responses = json.load(f)
    
    assert isinstance(mock_responses, dict)
    assert "mock_api_responses" in mock_responses
    
    print("✅ Mock data can be loaded")


if __name__ == "__main__":
    # Run tests if called directly
    pytest.main([__file__, "-v"])
