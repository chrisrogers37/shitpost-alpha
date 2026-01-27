# Test Database Consolidation

## Summary

All test operations now use a **single shared test database**: `test_shitpost_alpha.db`

## Changes Made

1. **`conftest.py`**: Updated to use `test_shitpost_alpha.db` as the shared test database
   - Fixed cleanup logic to properly remove the database file after tests
   - All tests that use the `test_db_client` fixture now share the same database

2. **`test_full_pipeline.py`**: Updated to use the shared `test_db_client` fixture instead of creating its own `test_pipeline.db`

3. **`test_setup_verification.py`**: Updated to use in-memory database for config testing

4. **`test_database_client.py`**: Updated to use in-memory database since all tests are mocked

5. **`.gitignore`**: Added explicit patterns for test database files

## Test Database Configuration

- **Shared Database**: `test_shitpost_alpha.db` (created by `conftest.py`)
- **Scope**: Session-scoped fixture (shared across all tests in a test run)
- **Cleanup**: Automatically deleted after all tests complete
- **Location**: Project root directory

## Cleanup

To remove existing test database files:

```bash
rm -f test.db test_shitpost_alpha.db test_pipeline.db
```

These files will be automatically recreated when tests run and cleaned up after completion.

## Notes

- Tests that only test configuration (like `test_database_config.py`) use in-memory databases (`:memory:`) since they don't need persistent storage
- All mocked tests don't create actual database files
- The shared database is cleaned between tests by dropping and recreating tables
