"""
Service-Specific Loggers
Provides specialized loggers for different services.
"""

import logging
from typing import Optional, Any
from datetime import datetime

from .config import get_config


def get_service_logger(service: str, module_name: Optional[str] = None) -> logging.Logger:
    """Get a logger for a specific service.
    
    Args:
        service: Service name (s3, database, llm, cli, etc.)
        module_name: Optional module name for logger hierarchy
        
    Returns:
        Configured logger for the service
    """
    config = get_config()
    
    # Check if service is enabled
    if not config.is_service_enabled(service):
        return _create_disabled_logger(service)
    
    # Build logger name
    if module_name:
        logger_name = f"{service}.{module_name}"
    else:
        logger_name = service
    
    logger = logging.getLogger(logger_name)
    
    # Configure logger level
    logger.setLevel(config.get_python_log_level())
    
    return logger


def _create_disabled_logger(service: str) -> logging.Logger:
    """Create a disabled logger for a service.
    
    Args:
        service: Service name
        
    Returns:
        Disabled logger
    """
    logger = logging.getLogger(f"{service}.disabled")
    logger.disabled = True
    return logger


class _BaseServiceLogger:
    """Shared scaffolding for the service loggers.

    Holds the underlying stdlib logger and emits a message with the standard
    ``extra`` envelope. Private on purpose — not exported from the package.
    """

    def __init__(self, service: str, module_name: Optional[str] = None):
        self.service = service
        self.logger = get_service_logger(service, module_name)

    def _emit(
        self,
        level: str,
        msg: str,
        fields: dict,
        suffix: Optional[str] = None,
    ) -> None:
        """Emit ``msg`` at ``level`` with the standard ``extra`` envelope.

        ``fields`` is the per-call ``extra`` payload (``operation`` plus any
        method-specific keys, with the caller's ``**kwargs`` already merged in
        last so it overrides — matching the original inline dict literals).
        ``self.service`` is injected first so a caller-supplied ``service`` in
        ``fields`` still wins. When ``suffix`` is truthy it is appended as
        `` (suffix)``; callers pass ``None`` when absent, so no trailing
        `` (...)`` ever appears otherwise.

        Taking ``fields`` as a dict (rather than ``**fields``) is deliberate:
        callers legitimately pass keys like ``operation`` in ``**kwargs``
        (e.g. ``progress(25, operation="harvest_posts")``), which would collide
        with a formal parameter of the same name.
        """
        if suffix:
            msg = f"{msg} ({suffix})"
        getattr(self.logger, level)(
            msg,
            extra={'service': self.service, **fields},
        )


class S3Logger(_BaseServiceLogger):
    """Logger for S3 operations."""

    def __init__(self, module_name: Optional[str] = None):
        """Initialize S3 logger.

        Args:
            module_name: Optional module name
        """
        super().__init__("s3", module_name)

    def uploading(self, key: str, **kwargs):
        """Log S3 upload start.

        Args:
            key: S3 object key
            **kwargs: Additional context
        """
        self._emit('info', f"📁 Uploading to S3: {key}",
                   {'operation': 'upload', 'key': key, **kwargs})

    def uploaded(self, key: str, size: Optional[str] = None, **kwargs):
        """Log successful S3 upload.

        Args:
            key: S3 object key
            size: File size (optional)
            **kwargs: Additional context
        """
        self._emit('info', f"✅ Uploaded to S3: {key}",
                   {'operation': 'upload_success', 'key': key, 'size': size, **kwargs},
                   suffix=size if size else None)

    def downloading(self, key: str, **kwargs):
        """Log S3 download start.

        Args:
            key: S3 object key
            **kwargs: Additional context
        """
        self._emit('info', f"📥 Downloading from S3: {key}",
                   {'operation': 'download', 'key': key, **kwargs})

    def downloaded(self, key: str, size: Optional[str] = None, **kwargs):
        """Log successful S3 download.

        Args:
            key: S3 object key
            size: File size (optional)
            **kwargs: Additional context
        """
        self._emit('info', f"✅ Downloaded from S3: {key}",
                   {'operation': 'download_success', 'key': key, 'size': size, **kwargs},
                   suffix=size if size else None)

    def checking_exists(self, key: str, **kwargs):
        """Log S3 existence check.

        Args:
            key: S3 object key
            **kwargs: Additional context
        """
        self._emit('debug', f"🔍 Checking S3 object exists: {key}",
                   {'operation': 'exists', 'key': key, **kwargs})

    def exists(self, key: str, exists: bool, **kwargs):
        """Log S3 existence check result.

        Args:
            key: S3 object key
            exists: Whether object exists
            **kwargs: Additional context
        """
        status = "✅ Exists" if exists else "❌ Not found"
        self._emit('debug', f"{status}: {key}",
                   {'operation': 'exists_result', 'key': key, 'exists': exists, **kwargs})


class DatabaseLogger(_BaseServiceLogger):
    """Logger for database operations."""

    def __init__(self, module_name: Optional[str] = None):
        """Initialize database logger.

        Args:
            module_name: Optional module name
        """
        super().__init__("database", module_name)

    def executing_query(self, query_type: str, **kwargs):
        """Log database query execution.

        Args:
            query_type: Type of query
            **kwargs: Additional context
        """
        self._emit('debug', f"🗄️ Executing {query_type} query",
                   {'operation': 'query', 'query_type': query_type, **kwargs})

    def query_result(self, query_type: str, rows: Optional[int] = None, **kwargs):
        """Log database query result.

        Args:
            query_type: Type of query
            rows: Number of rows (optional)
            **kwargs: Additional context
        """
        self._emit('debug', f"✅ Query completed: {query_type}",
                   {'operation': 'query_result', 'query_type': query_type, 'rows': rows, **kwargs},
                   suffix=f"{rows} rows" if rows is not None else None)

    def inserting(self, table: str, count: int = 1, **kwargs):
        """Log database insert operation.

        Args:
            table: Table name
            count: Number of records
            **kwargs: Additional context
        """
        self._emit('info', f"💾 Inserting {count} record(s) into {table}",
                   {'operation': 'insert', 'table': table, 'count': count, **kwargs})

    def inserted(self, table: str, count: int = 1, **kwargs):
        """Log successful database insert.

        Args:
            table: Table name
            count: Number of records
            **kwargs: Additional context
        """
        self._emit('info', f"✅ Inserted {count} record(s) into {table}",
                   {'operation': 'insert_success', 'table': table, 'count': count, **kwargs})


class LLMLogger(_BaseServiceLogger):
    """Logger for LLM operations."""

    def __init__(self, module_name: Optional[str] = None):
        """Initialize LLM logger.

        Args:
            module_name: Optional module name
        """
        super().__init__("llm", module_name)

    def api_call_start(self, model: str, **kwargs):
        """Log LLM API call start.

        Args:
            model: Model name
            **kwargs: Additional context
        """
        self._emit('info', f"🤖 Calling LLM API: {model}",
                   {'operation': 'api_call', 'model': model, **kwargs})

    def api_call_success(self, model: str, tokens: Optional[int] = None, **kwargs):
        """Log successful LLM API call.

        Args:
            model: Model name
            tokens: Number of tokens (optional)
            **kwargs: Additional context
        """
        self._emit('info', f"✅ LLM API call completed: {model}",
                   {'operation': 'api_call_success', 'model': model, 'tokens': tokens, **kwargs},
                   suffix=f"{tokens} tokens" if tokens is not None else None)

    def analyzing(self, item: str, **kwargs):
        """Log LLM analysis start.

        Args:
            item: Item being analyzed
            **kwargs: Additional context
        """
        self._emit('info', f"🔬 Analyzing: {item[:50]}...",
                   {'operation': 'analyze', 'item': item[:100], **kwargs})

    def analysis_complete(self, item: str, confidence: Optional[float] = None, **kwargs):
        """Log completed LLM analysis.

        Args:
            item: Item analyzed
            confidence: Confidence score (optional)
            **kwargs: Additional context
        """
        self._emit('info', f"✅ Analysis complete: {item[:50]}...",
                   {'operation': 'analyze_success', 'item': item[:100], 'confidence': confidence, **kwargs},
                   suffix=f"confidence: {confidence:.1%}" if confidence is not None else None)


class CLILogger(_BaseServiceLogger):
    """Logger for CLI operations."""

    def __init__(self, module_name: Optional[str] = None):
        """Initialize CLI logger.

        Args:
            module_name: Optional module name
        """
        super().__init__("cli", module_name)

    def operation_start(self, operation: str, **kwargs):
        """Log CLI operation start.

        Args:
            operation: Operation name
            **kwargs: Additional context
        """
        self._emit('info', f"🚀 Starting: {operation}",
                   {'operation': operation, 'status': 'start', **kwargs})

    def operation_complete(self, operation: str, **kwargs):
        """Log successful CLI operation completion.

        Args:
            operation: Operation name
            **kwargs: Additional context
        """
        self._emit('info', f"✅ Completed: {operation}",
                   {'operation': operation, 'status': 'complete', **kwargs})

    def operation_error(self, operation: str, error: str, **kwargs):
        """Log CLI operation error.

        Args:
            operation: Operation name
            error: Error message
            **kwargs: Additional context
        """
        self._emit('error', f"❌ Error in {operation}: {error}",
                   {'operation': operation, 'status': 'error', 'error': error, **kwargs})

    def progress(self, current: int, total: Optional[int] = None, **kwargs):
        """Log CLI operation progress.

        Args:
            current: Current progress
            total: Total items (optional)
            **kwargs: Additional context
        """
        if total is not None:
            percentage = (current / total) * 100
            message = f"📊 Progress: {current}/{total} ({percentage:.1f}%)"
        else:
            message = f"📊 Progress: {current}"
        self._emit('info', message,
                   {'operation': 'progress', 'current': current, 'total': total, **kwargs})


# Convenience functions for getting service loggers
def get_s3_logger(module_name: Optional[str] = None) -> S3Logger:
    """Get S3 logger.
    
    Args:
        module_name: Optional module name
        
    Returns:
        S3Logger instance
    """
    return S3Logger(module_name)


def get_database_logger(module_name: Optional[str] = None) -> DatabaseLogger:
    """Get database logger.
    
    Args:
        module_name: Optional module name
        
    Returns:
        DatabaseLogger instance
    """
    return DatabaseLogger(module_name)


def get_llm_logger(module_name: Optional[str] = None) -> LLMLogger:
    """Get LLM logger.
    
    Args:
        module_name: Optional module name
        
    Returns:
        LLMLogger instance
    """
    return LLMLogger(module_name)


def get_cli_logger(module_name: Optional[str] = None) -> CLILogger:
    """Get CLI logger.
    
    Args:
        module_name: Optional module name
        
    Returns:
        CLILogger instance
    """
    return CLILogger(module_name)
