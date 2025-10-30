"""
Tests for service-specific loggers - S3, Database, LLM, CLI loggers.
Tests that will break if service logger functionality changes.
"""

import pytest
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime

from shit.logging.service_loggers import (
    get_service_logger,
    S3Logger,
    DatabaseLogger,
    LLMLogger,
    CLILogger,
    get_s3_logger,
    get_database_logger,
    get_llm_logger,
    get_cli_logger,
    _create_disabled_logger
)
from shit.logging.config import LoggingConfig, LogLevel


class TestGetServiceLogger:
    """Test get_service_logger function."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = MagicMock()
        config.is_service_enabled.return_value = True
        config.get_python_log_level.return_value = logging.INFO
        return config
    
    def test_get_service_logger_enabled(self, mock_config):
        """Test getting enabled service logger."""
        with patch('shit.logging.service_loggers.get_config', return_value=mock_config):
            logger = get_service_logger("s3")
            
            assert isinstance(logger, logging.Logger)
            assert logger.name == "s3"
            mock_config.is_service_enabled.assert_called_once_with("s3")
    
    def test_get_service_logger_with_module(self, mock_config):
        """Test getting service logger with module name."""
        with patch('shit.logging.service_loggers.get_config', return_value=mock_config):
            logger = get_service_logger("s3", "upload")
            
            assert isinstance(logger, logging.Logger)
            assert logger.name == "s3.upload"
    
    def test_get_service_logger_disabled(self, mock_config):
        """Test getting disabled service logger."""
        mock_config.is_service_enabled.return_value = False
        
        with patch('shit.logging.service_loggers.get_config', return_value=mock_config):
            logger = get_service_logger("s3")
            
            assert isinstance(logger, logging.Logger)
            assert logger.name == "s3.disabled"
            assert logger.disabled is True
    
    def test_get_service_logger_unknown_service(self, mock_config):
        """Test getting logger for unknown service."""
        with patch('shit.logging.service_loggers.get_config', return_value=mock_config):
            logger = get_service_logger("unknown_service")
            
            assert isinstance(logger, logging.Logger)
            assert logger.name == "unknown_service"


class TestCreateDisabledLogger:
    """Test _create_disabled_logger function."""
    
    def test_create_disabled_logger(self):
        """Test creating disabled logger."""
        logger = _create_disabled_logger("test_service")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_service.disabled"
        assert logger.disabled is True


class TestS3Logger:
    """Test S3Logger class."""
    
    @pytest.fixture
    def s3_logger(self):
        """S3 logger instance."""
        with patch('shit.logging.service_loggers.get_service_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            return S3Logger("upload")
    
    def test_s3_logger_initialization(self, s3_logger):
        """Test S3 logger initialization."""
        assert hasattr(s3_logger, 'logger')
        assert hasattr(s3_logger, 'uploading')
        assert hasattr(s3_logger, 'uploaded')
        assert hasattr(s3_logger, 'downloading')
        assert hasattr(s3_logger, 'downloaded')
        assert hasattr(s3_logger, 'checking_exists')
        assert hasattr(s3_logger, 'exists')
    
    def test_uploading(self, s3_logger):
        """Test uploading log method."""
        s3_logger.uploading("test-key", bucket="test-bucket")
        
        s3_logger.logger.info.assert_called_once()
        call_args = s3_logger.logger.info.call_args
        assert "📁 Uploading to S3: test-key" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 's3'
        assert call_args[1]['extra']['operation'] == 'upload'
        assert call_args[1]['extra']['key'] == 'test-key'
        assert call_args[1]['extra']['bucket'] == 'test-bucket'
    
    def test_uploaded(self, s3_logger):
        """Test uploaded log method."""
        s3_logger.uploaded("test-key", size="1KB", bucket="test-bucket")
        
        s3_logger.logger.info.assert_called_once()
        call_args = s3_logger.logger.info.call_args
        assert "✅ Uploaded to S3: test-key (1KB)" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 's3'
        assert call_args[1]['extra']['operation'] == 'upload_success'
        assert call_args[1]['extra']['key'] == 'test-key'
        assert call_args[1]['extra']['size'] == '1KB'
    
    def test_uploaded_without_size(self, s3_logger):
        """Test uploaded log method without size."""
        s3_logger.uploaded("test-key")
        
        s3_logger.logger.info.assert_called_once()
        call_args = s3_logger.logger.info.call_args
        assert "✅ Uploaded to S3: test-key" in call_args[0][0]
        assert call_args[1]['extra']['size'] is None
    
    def test_downloading(self, s3_logger):
        """Test downloading log method."""
        s3_logger.downloading("test-key", bucket="test-bucket")
        
        s3_logger.logger.info.assert_called_once()
        call_args = s3_logger.logger.info.call_args
        assert "📥 Downloading from S3: test-key" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 's3'
        assert call_args[1]['extra']['operation'] == 'download'
        assert call_args[1]['extra']['key'] == 'test-key'
    
    def test_downloaded(self, s3_logger):
        """Test downloaded log method."""
        s3_logger.downloaded("test-key", size="2KB")
        
        s3_logger.logger.info.assert_called_once()
        call_args = s3_logger.logger.info.call_args
        assert "✅ Downloaded from S3: test-key (2KB)" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 's3'
        assert call_args[1]['extra']['operation'] == 'download_success'
        assert call_args[1]['extra']['key'] == 'test-key'
        assert call_args[1]['extra']['size'] == '2KB'
    
    def test_checking_exists(self, s3_logger):
        """Test checking_exists log method."""
        s3_logger.checking_exists("test-key")
        
        s3_logger.logger.debug.assert_called_once()
        call_args = s3_logger.logger.debug.call_args
        assert "🔍 Checking S3 object exists: test-key" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 's3'
        assert call_args[1]['extra']['operation'] == 'exists'
        assert call_args[1]['extra']['key'] == 'test-key'
    
    def test_exists_true(self, s3_logger):
        """Test exists log method with True."""
        s3_logger.exists("test-key", True)
        
        s3_logger.logger.debug.assert_called_once()
        call_args = s3_logger.logger.debug.call_args
        assert "✅ Exists: test-key" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 's3'
        assert call_args[1]['extra']['operation'] == 'exists_result'
        assert call_args[1]['extra']['key'] == 'test-key'
        assert call_args[1]['extra']['exists'] is True
    
    def test_exists_false(self, s3_logger):
        """Test exists log method with False."""
        s3_logger.exists("test-key", False)
        
        s3_logger.logger.debug.assert_called_once()
        call_args = s3_logger.logger.debug.call_args
        assert "❌ Not found: test-key" in call_args[0][0]
        assert call_args[1]['extra']['exists'] is False


class TestDatabaseLogger:
    """Test DatabaseLogger class."""
    
    @pytest.fixture
    def db_logger(self):
        """Database logger instance."""
        with patch('shit.logging.service_loggers.get_service_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            return DatabaseLogger("operations")
    
    def test_database_logger_initialization(self, db_logger):
        """Test database logger initialization."""
        assert hasattr(db_logger, 'logger')
        assert hasattr(db_logger, 'executing_query')
        assert hasattr(db_logger, 'query_result')
        assert hasattr(db_logger, 'inserting')
        assert hasattr(db_logger, 'inserted')
    
    def test_executing_query(self, db_logger):
        """Test executing_query log method."""
        db_logger.executing_query("SELECT", table="users")
        
        db_logger.logger.debug.assert_called_once()
        call_args = db_logger.logger.debug.call_args
        assert "🗄️ Executing SELECT query" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'database'
        assert call_args[1]['extra']['operation'] == 'query'
        assert call_args[1]['extra']['query_type'] == 'SELECT'
        assert call_args[1]['extra']['table'] == 'users'
    
    def test_query_result(self, db_logger):
        """Test query_result log method."""
        db_logger.query_result("SELECT", rows=5, table="users")
        
        db_logger.logger.debug.assert_called_once()
        call_args = db_logger.logger.debug.call_args
        assert "✅ Query completed: SELECT (5 rows)" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'database'
        assert call_args[1]['extra']['operation'] == 'query_result'
        assert call_args[1]['extra']['query_type'] == 'SELECT'
        assert call_args[1]['extra']['rows'] == 5
    
    def test_query_result_without_rows(self, db_logger):
        """Test query_result log method without rows."""
        db_logger.query_result("INSERT")
        
        db_logger.logger.debug.assert_called_once()
        call_args = db_logger.logger.debug.call_args
        assert "✅ Query completed: INSERT" in call_args[0][0]
        assert call_args[1]['extra']['rows'] is None
    
    def test_inserting(self, db_logger):
        """Test inserting log method."""
        db_logger.inserting("users", count=3, batch_id="batch-123")
        
        db_logger.logger.info.assert_called_once()
        call_args = db_logger.logger.info.call_args
        assert "💾 Inserting 3 record(s) into users" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'database'
        assert call_args[1]['extra']['operation'] == 'insert'
        assert call_args[1]['extra']['table'] == 'users'
        assert call_args[1]['extra']['count'] == 3
        assert call_args[1]['extra']['batch_id'] == 'batch-123'
    
    def test_inserted(self, db_logger):
        """Test inserted log method."""
        db_logger.inserted("users", count=3, batch_id="batch-123")
        
        db_logger.logger.info.assert_called_once()
        call_args = db_logger.logger.info.call_args
        assert "✅ Inserted 3 record(s) into users" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'database'
        assert call_args[1]['extra']['operation'] == 'insert_success'
        assert call_args[1]['extra']['table'] == 'users'
        assert call_args[1]['extra']['count'] == 3


class TestLLMLogger:
    """Test LLMLogger class."""
    
    @pytest.fixture
    def llm_logger(self):
        """LLM logger instance."""
        with patch('shit.logging.service_loggers.get_service_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            return LLMLogger("client")
    
    def test_llm_logger_initialization(self, llm_logger):
        """Test LLM logger initialization."""
        assert hasattr(llm_logger, 'logger')
        assert hasattr(llm_logger, 'api_call_start')
        assert hasattr(llm_logger, 'api_call_success')
        assert hasattr(llm_logger, 'analyzing')
        assert hasattr(llm_logger, 'analysis_complete')
    
    def test_api_call_start(self, llm_logger):
        """Test api_call_start log method."""
        llm_logger.api_call_start("gpt-4", provider="openai")
        
        llm_logger.logger.info.assert_called_once()
        call_args = llm_logger.logger.info.call_args
        assert "🤖 Calling LLM API: gpt-4" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'llm'
        assert call_args[1]['extra']['operation'] == 'api_call'
        assert call_args[1]['extra']['model'] == 'gpt-4'
        assert call_args[1]['extra']['provider'] == 'openai'
    
    def test_api_call_success(self, llm_logger):
        """Test api_call_success log method."""
        llm_logger.api_call_success("gpt-4", tokens=150, provider="openai")
        
        llm_logger.logger.info.assert_called_once()
        call_args = llm_logger.logger.info.call_args
        assert "✅ LLM API call completed: gpt-4 (150 tokens)" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'llm'
        assert call_args[1]['extra']['operation'] == 'api_call_success'
        assert call_args[1]['extra']['model'] == 'gpt-4'
        assert call_args[1]['extra']['tokens'] == 150
    
    def test_api_call_success_without_tokens(self, llm_logger):
        """Test api_call_success log method without tokens."""
        llm_logger.api_call_success("gpt-4")
        
        llm_logger.logger.info.assert_called_once()
        call_args = llm_logger.logger.info.call_args
        assert "✅ LLM API call completed: gpt-4" in call_args[0][0]
        assert call_args[1]['extra']['tokens'] is None
    
    def test_analyzing(self, llm_logger):
        """Test analyzing log method."""
        long_text = "A" * 100  # Long text to test truncation
        llm_logger.analyzing(long_text, analysis_type="financial")
        
        llm_logger.logger.info.assert_called_once()
        call_args = llm_logger.logger.info.call_args
        assert "🔬 Analyzing: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA..." in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'llm'
        assert call_args[1]['extra']['operation'] == 'analyze'
        assert call_args[1]['extra']['item'] == long_text[:100]  # Truncated
        assert call_args[1]['extra']['analysis_type'] == 'financial'
    
    def test_analysis_complete(self, llm_logger):
        """Test analysis_complete log method."""
        long_text = "A" * 100  # Long text to test truncation
        llm_logger.analysis_complete(long_text, confidence=0.85, analysis_type="financial")
        
        llm_logger.logger.info.assert_called_once()
        call_args = llm_logger.logger.info.call_args
        assert "✅ Analysis complete: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA... (confidence: 85.0%)" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'llm'
        assert call_args[1]['extra']['operation'] == 'analyze_success'
        assert call_args[1]['extra']['item'] == long_text[:100]  # Truncated
        assert call_args[1]['extra']['confidence'] == 0.85
    
    def test_analysis_complete_without_confidence(self, llm_logger):
        """Test analysis_complete log method without confidence."""
        llm_logger.analysis_complete("test item")
        
        llm_logger.logger.info.assert_called_once()
        call_args = llm_logger.logger.info.call_args
        assert "✅ Analysis complete: test item..." in call_args[0][0]
        assert call_args[1]['extra']['confidence'] is None


class TestCLILogger:
    """Test CLILogger class."""
    
    @pytest.fixture
    def cli_logger(self):
        """CLI logger instance."""
        with patch('shit.logging.service_loggers.get_service_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            return CLILogger("harvester")
    
    def test_cli_logger_initialization(self, cli_logger):
        """Test CLI logger initialization."""
        assert hasattr(cli_logger, 'logger')
        assert hasattr(cli_logger, 'operation_start')
        assert hasattr(cli_logger, 'operation_complete')
        assert hasattr(cli_logger, 'operation_error')
        assert hasattr(cli_logger, 'progress')
    
    def test_operation_start(self, cli_logger):
        """Test operation_start log method."""
        cli_logger.operation_start("harvest_posts", module="truth_social")
        
        cli_logger.logger.info.assert_called_once()
        call_args = cli_logger.logger.info.call_args
        assert "🚀 Starting: harvest_posts" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'cli'
        assert call_args[1]['extra']['operation'] == 'harvest_posts'
        assert call_args[1]['extra']['status'] == 'start'
        assert call_args[1]['extra']['module'] == 'truth_social'
    
    def test_operation_complete(self, cli_logger):
        """Test operation_complete log method."""
        cli_logger.operation_complete("harvest_posts", posts_count=100)
        
        cli_logger.logger.info.assert_called_once()
        call_args = cli_logger.logger.info.call_args
        assert "✅ Completed: harvest_posts" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'cli'
        assert call_args[1]['extra']['operation'] == 'harvest_posts'
        assert call_args[1]['extra']['status'] == 'complete'
        assert call_args[1]['extra']['posts_count'] == 100
    
    def test_operation_error(self, cli_logger):
        """Test operation_error log method."""
        cli_logger.operation_error("harvest_posts", "Connection failed", module="truth_social")
        
        cli_logger.logger.error.assert_called_once()
        call_args = cli_logger.logger.error.call_args
        assert "❌ Error in harvest_posts: Connection failed" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'cli'
        assert call_args[1]['extra']['operation'] == 'harvest_posts'
        assert call_args[1]['extra']['status'] == 'error'
        assert call_args[1]['extra']['error'] == 'Connection failed'
        assert call_args[1]['extra']['module'] == 'truth_social'
    
    def test_progress_with_total(self, cli_logger):
        """Test progress log method with total."""
        cli_logger.progress(25, 100, task="harvest_posts")
        
        cli_logger.logger.info.assert_called_once()
        call_args = cli_logger.logger.info.call_args
        assert "📊 Progress: 25/100 (25.0%)" in call_args[0][0]
        assert call_args[1]['extra']['service'] == 'cli'
        assert call_args[1]['extra']['operation'] == 'progress'
        assert call_args[1]['extra']['current'] == 25
        assert call_args[1]['extra']['total'] == 100
        assert call_args[1]['extra']['task'] == 'harvest_posts'  # This is a kwarg
    
    def test_progress_without_total(self, cli_logger):
        """Test progress log method without total."""
        cli_logger.progress(25, operation="harvest_posts")
        
        cli_logger.logger.info.assert_called_once()
        call_args = cli_logger.logger.info.call_args
        assert "📊 Progress: 25" in call_args[0][0]
        assert call_args[1]['extra']['current'] == 25
        assert call_args[1]['extra']['total'] is None


class TestConvenienceFunctions:
    """Test convenience functions for getting service loggers."""
    
    def test_get_s3_logger(self):
        """Test get_s3_logger function."""
        with patch('shit.logging.service_loggers.S3Logger') as mock_s3_logger_class:
            mock_logger = MagicMock()
            mock_s3_logger_class.return_value = mock_logger
            
            result = get_s3_logger("upload")
            mock_s3_logger_class.assert_called_once_with("upload")
            assert result == mock_logger
    
    def test_get_database_logger(self):
        """Test get_database_logger function."""
        with patch('shit.logging.service_loggers.DatabaseLogger') as mock_db_logger_class:
            mock_logger = MagicMock()
            mock_db_logger_class.return_value = mock_logger
            
            result = get_database_logger("operations")
            mock_db_logger_class.assert_called_once_with("operations")
            assert result == mock_logger
    
    def test_get_llm_logger(self):
        """Test get_llm_logger function."""
        with patch('shit.logging.service_loggers.LLMLogger') as mock_llm_logger_class:
            mock_logger = MagicMock()
            mock_llm_logger_class.return_value = mock_logger
            
            result = get_llm_logger("client")
            mock_llm_logger_class.assert_called_once_with("client")
            assert result == mock_logger
    
    def test_get_cli_logger(self):
        """Test get_cli_logger function."""
        with patch('shit.logging.service_loggers.CLILogger') as mock_cli_logger_class:
            mock_logger = MagicMock()
            mock_cli_logger_class.return_value = mock_logger
            
            result = get_cli_logger("harvester")
            mock_cli_logger_class.assert_called_once_with("harvester")
            assert result == mock_logger


class TestServiceLoggerEdgeCases:
    """Test edge cases and error scenarios for service loggers."""
    
    def test_s3_logger_with_empty_key(self):
        """Test S3 logger with empty key."""
        with patch('shit.logging.service_loggers.get_service_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            s3_logger = S3Logger()
            s3_logger.uploading("")
            
            call_args = s3_logger.logger.info.call_args
            assert "📁 Uploading to S3: " in call_args[0][0]
            assert call_args[1]['extra']['key'] == ""
    
    def test_database_logger_with_zero_count(self):
        """Test database logger with zero count."""
        with patch('shit.logging.service_loggers.get_service_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            db_logger = DatabaseLogger()
            db_logger.inserting("users", count=0)
            
            call_args = db_logger.logger.info.call_args
            assert "💾 Inserting 0 record(s) into users" in call_args[0][0]
            assert call_args[1]['extra']['count'] == 0
    
    def test_llm_logger_with_very_long_item(self):
        """Test LLM logger with very long item text."""
        with patch('shit.logging.service_loggers.get_service_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            llm_logger = LLMLogger()
            long_text = "A" * 200  # Longer than truncation limit
            llm_logger.analyzing(long_text)
            
            call_args = llm_logger.logger.info.call_args
            assert "🔬 Analyzing: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA..." in call_args[0][0]
            assert call_args[1]['extra']['item'] == long_text[:100]  # Truncated
    
    def test_cli_logger_with_unicode_operation(self):
        """Test CLI logger with unicode operation name."""
        with patch('shit.logging.service_loggers.get_service_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            cli_logger = CLILogger()
            cli_logger.operation_start("测试操作")
            
            call_args = cli_logger.logger.info.call_args
            assert "🚀 Starting: 测试操作" in call_args[0][0]
            assert call_args[1]['extra']['operation'] == "测试操作"
    
    def test_service_logger_with_none_module(self):
        """Test service logger with None module name."""
        with patch('shit.logging.service_loggers.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.is_service_enabled.return_value = True
            mock_config.get_python_log_level.return_value = logging.INFO
            mock_get_config.return_value = mock_config
            
            logger = get_service_logger("s3", None)
            assert logger.name == "s3"
    
    def test_service_logger_with_empty_module(self):
        """Test service logger with empty module name."""
        with patch('shit.logging.service_loggers.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.is_service_enabled.return_value = True
            mock_config.get_python_log_level.return_value = logging.INFO
            mock_get_config.return_value = mock_config
            
            logger = get_service_logger("s3", "")
            assert logger.name == "s3"
    
    def test_disabled_logger_creation(self):
        """Test disabled logger creation."""
        logger = _create_disabled_logger("test")
        assert logger.name == "test.disabled"
        assert logger.disabled is True
    
    def test_service_logger_with_special_characters(self):
        """Test service logger with special characters in service name."""
        with patch('shit.logging.service_loggers.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.is_service_enabled.return_value = True
            mock_config.get_python_log_level.return_value = logging.INFO
            mock_get_config.return_value = mock_config
            
            logger = get_service_logger("test-service_123")
            assert logger.name == "test-service_123"
