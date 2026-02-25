"""
Shitpost Alpha Core Package

This package contains the core functionality for the Shitpost Alpha application,
including database operations, S3 integration, LLM processing, and logging.
"""

__version__ = "1.0.0"
__author__ = "Shitpost Alpha Team"

from shit.services import db_service, s3_service, db_and_s3_service

__all__ = [
    "db_service",
    "s3_service",
    "db_and_s3_service",
]
