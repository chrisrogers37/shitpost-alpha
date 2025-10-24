# Shitpost Alpha Test Suite

## 🧪 Overview

This directory contains the comprehensive test suite for the Shitpost Alpha project. The test structure mirrors the main project structure and provides complete coverage of all functionality.

## 📁 Directory Structure

```
shit_tests/
├── conftest.py                    # Global test configuration and fixtures
├── pytest.ini                    # Pytest configuration
├── requirements-test.txt          # Test-specific dependencies
├── run_tests.py                   # Test runner script
├── test_setup_verification.py    # Setup verification tests
├── test_shitpost_alpha.py         # Main orchestrator tests
├── shit/                          # Core infrastructure tests
│   ├── config/
│   │   └── test_shitpost_settings.py
│   ├── db/
│   │   ├── test_database_client.py
│   │   ├── test_database_config.py
│   │   ├── test_database_operations.py
│   │   ├── test_database_utils.py
│   │   └── test_data_models.py
│   ├── llm/
│   │   ├── test_llm_client.py
│   │   └── test_prompts.py
│   ├── s3/
│   │   ├── test_s3_client.py
│   │   ├── test_s3_config.py
│   │   ├── test_s3_data_lake.py
│   │   └── test_s3_models.py
│   └── utils/
│       └── test_error_handling.py
├── shitvault/                     # Database and S3 processing tests
│   ├── test_cli.py
│   ├── test_prediction_operations.py
│   ├── test_s3_processor.py
│   ├── test_shitpost_models.py
│   ├── test_shitpost_operations.py
│   └── test_statistics.py
├── shitposts/                     # Content harvesting tests
│   ├── test_cli.py
│   └── test_truth_social_s3_harvester.py
├── shitpost_ai/                   # AI analysis tests
│   ├── test_cli.py
│   └── test_shitpost_analyzer.py
├── integration/                   # End-to-end integration tests
│   ├── test_full_pipeline.py
│   ├── test_s3_to_database.py
│   ├── test_harvesting_pipeline.py
│   └── test_analysis_pipeline.py
└── fixtures/                      # Test data and mocks
    ├── test_data/
    │   ├── sample_shitposts.json
    │   ├── sample_llm_responses.json
    │   └── sample_s3_data.json
    └── mock_responses/
        ├── truth_social_api.json
        └── llm_responses.json
```

## 🚀 Quick Start

### 1. Install Test Dependencies

```bash
# Install test-specific dependencies
pip install -r shit_tests/requirements-test.txt
```

### 2. Run Tests

```bash
# Run all tests
python shit_tests/run_tests.py all

# Run specific test categories
python shit_tests/run_tests.py unit
python shit_tests/run_tests.py integration
python shit_tests/run_tests.py e2e

# Run with coverage
python shit_tests/run_tests.py coverage

# Run specific test file
python shit_tests/run_tests.py specific shit_tests/shit/db/test_database_config.py
```

### 3. Verify Setup

```bash
# Run setup verification
python -m pytest shit_tests/test_setup_verification.py -v
```

## 🧪 Test Categories

### Unit Tests
- **Purpose**: Test individual components in isolation
- **Coverage**: Database operations, S3 operations, LLM client, configuration
- **Dependencies**: Mocked external services
- **Run**: `python shit_tests/run_tests.py unit`

### Integration Tests
- **Purpose**: Test component interactions with real services
- **Coverage**: Database connectivity, S3 storage, LLM API calls
- **Dependencies**: Test database, test S3 bucket, test LLM API keys
- **Run**: `python shit_tests/run_tests.py integration`

### End-to-End Tests
- **Purpose**: Test complete workflows with real API calls
- **Coverage**: Full pipeline (API → S3 → Database → LLM → Database)
- **Dependencies**: Real Truth Social API, real S3, real LLM APIs
- **Run**: `python shit_tests/run_tests.py e2e`

## 🛠️ Test Configuration

### Database Testing
- **Test Database**: `sqlite+aiosqlite:///./test_shitpost_alpha.db`
- **Isolation**: Separate from production database
- **Cleanup**: Automatic cleanup after tests

### S3 Testing
- **Test Bucket**: `shitpost-alpha-test`
- **Isolation**: Separate from production S3
- **Mocking**: Option to mock S3 operations for unit tests

### LLM Testing
- **Test API Keys**: Use test/sandbox API keys
- **Mocking**: Option to mock LLM responses for unit tests
- **Rate Limiting**: Respect API rate limits in integration tests

## 📊 Test Data

### Sample Data
- **`sample_shitposts.json`**: Real Truth Social post data
- **`sample_llm_responses.json`**: Expected LLM analysis responses
- **`sample_s3_data.json`**: S3 storage format examples

### Mock Responses
- **`truth_social_api.json`**: Mock Truth Social API responses
- **`llm_responses.json`**: Mock LLM API responses

## 🔧 Test Fixtures

### Global Fixtures (`conftest.py`)
- `test_db_config`: Test database configuration
- `test_db_client`: Test database client
- `test_s3_config`: Test S3 configuration
- `test_llm_config`: Test LLM configuration
- `sample_shitpost_data`: Sample shitpost data
- `sample_llm_response`: Sample LLM response
- `sample_s3_data`: Sample S3 data

### Test Markers
- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.e2e`: End-to-end tests
- `@pytest.mark.slow`: Slow-running tests
- `@pytest.mark.database`: Tests requiring database
- `@pytest.mark.s3`: Tests requiring S3
- `@pytest.mark.llm`: Tests requiring LLM API
- `@pytest.mark.api`: Tests requiring external API

## 📈 Coverage Goals

- **Unit Tests**: 90%+ coverage for all modules
- **Integration Tests**: 80%+ coverage for critical workflows
- **End-to-End Tests**: 100% coverage for main user journeys
- **Error Handling**: 100% coverage for error conditions

## 🚨 Test Execution

### Local Development
```bash
# Run tests during development
python shit_tests/run_tests.py unit

# Run with verbose output
python -m pytest shit_tests/ -v

# Run specific test file
python -m pytest shit_tests/shit/db/test_database_config.py -v
```

### CI/CD Integration
```bash
# Run all tests with coverage
python shit_tests/run_tests.py coverage

# Run tests in parallel
python shit_tests/run_tests.py parallel

# Run slow tests
python shit_tests/run_tests.py slow
```

## 🔒 Security and Isolation

### Test Environment Isolation
1. **Database**: Uses separate test database (`test_shitpost_alpha.db`)
2. **S3**: Uses test bucket or local storage
3. **LLM**: Uses test API keys and sandbox environments
4. **Configuration**: Uses test-specific environment variables
5. **Data**: Uses synthetic or anonymized test data

### Test Data Security
- No production data in tests
- Synthetic data generation for realistic testing
- Mock external API calls where appropriate
- Secure test configuration management

## 📝 Test Documentation

### Test Case Documentation
Each test includes:
- Clear test name describing the scenario
- Setup and teardown procedures
- Expected behavior and assertions
- Error conditions and edge cases
- Performance expectations where applicable

### Test Results Reporting
- Coverage reports with detailed breakdowns
- Performance metrics for integration tests
- Error logs and debugging information
- Test execution time and resource usage

## 🎯 Implementation Status

### ✅ Completed
- [x] Test directory structure setup
- [x] Test configuration and fixtures
- [x] Unit tests for core modules (database, S3, LLM)
- [x] Integration test framework
- [x] Test data and mock responses
- [x] Test runner script
- [x] Setup verification tests

### 🚧 In Progress
- [ ] Complete unit tests for all modules
- [ ] End-to-end integration tests
- [ ] Performance and load tests
- [ ] Test coverage reporting
- [ ] CI/CD integration

### 📋 Planned
- [ ] Advanced test scenarios
- [ ] Test data generation utilities
- [ ] Test performance optimization
- [ ] Test maintenance automation

## 🔄 Continuous Improvement

### Test Maintenance
- Regular test data updates
- Test case review and optimization
- Coverage monitoring and improvement
- Test maintenance effort tracking

### Test Quality Metrics
- Test execution time
- Test reliability (flaky test detection)
- Coverage trends
- Test maintenance effort

## 📞 Support

For questions about the test suite:
- Check the test implementation guide in `reference_docs/testing_implementation_guide.md`
- Review test examples in the test files
- Run setup verification: `python -m pytest shit_tests/test_setup_verification.py -v`

This comprehensive test suite ensures robust, reliable, and maintainable code while providing confidence in the system's functionality and performance.
