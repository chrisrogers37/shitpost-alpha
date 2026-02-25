"""
Service Initialization Factory

Async context managers for initializing and cleaning up database and S3
services from centralized settings. Replaces the 12-line boilerplate
that was copy-pasted across CLI and event consumer modules.

Usage::

    from shit.services import db_service, s3_service, db_and_s3_service

    async with db_service() as db_client:
        async with db_client.get_session() as session:
            ...

    async with db_and_s3_service() as (db_client, s3_data_lake):
        ...
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Tuple

from shit.config.shitpost_settings import settings
from shit.db import DatabaseConfig, DatabaseClient
from shit.s3 import S3Config, S3DataLake


@asynccontextmanager
async def db_service() -> AsyncGenerator[DatabaseClient, None]:
    """Initialize and yield a DatabaseClient, cleaning up on exit.

    Reads connection settings from the global ``settings`` singleton.

    Yields:
        Initialized DatabaseClient ready for use.
    """
    db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
    db_client = DatabaseClient(db_config)
    await db_client.initialize()
    try:
        yield db_client
    finally:
        await db_client.cleanup()


@asynccontextmanager
async def s3_service() -> AsyncGenerator[S3DataLake, None]:
    """Initialize and yield an S3DataLake, cleaning up on exit.

    Reads S3 settings from the global ``settings`` singleton.

    Yields:
        Initialized S3DataLake ready for use.
    """
    s3_config = S3Config(
        bucket_name=settings.S3_BUCKET_NAME,
        access_key_id=settings.AWS_ACCESS_KEY_ID,
        secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region=settings.AWS_REGION,
    )
    s3_data_lake = S3DataLake(s3_config)
    await s3_data_lake.initialize()
    try:
        yield s3_data_lake
    finally:
        await s3_data_lake.cleanup()


@asynccontextmanager
async def db_and_s3_service() -> AsyncGenerator[Tuple[DatabaseClient, S3DataLake], None]:
    """Initialize and yield both DatabaseClient and S3DataLake.

    Both are cleaned up when the context exits, even if an error occurs.
    Database cleanup runs first, then S3 cleanup.

    Yields:
        Tuple of (DatabaseClient, S3DataLake), both initialized.
    """
    async with db_service() as db_client:
        async with s3_service() as s3_data_lake:
            yield db_client, s3_data_lake
