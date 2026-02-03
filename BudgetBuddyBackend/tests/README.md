# BudgetBuddy Backend Test Suite

Comprehensive test suite for the BudgetBuddy backend API and services.

## Test Structure

```
tests/
├── conftest.py                  # Pytest fixtures and configuration
├── test_models.py              # Unit tests for data models
├── test_db_models.py           # Unit tests for database models
├── test_tools.py               # Unit tests for agent tools
├── test_llm_service.py         # Unit tests for LLM service wrapper
├── test_orchestrator.py        # Unit tests for message orchestrator
├── test_plan_generator.py      # Unit tests for plan generation
├── test_statement_analyzer.py  # Unit tests for statement analysis
└── test_api_endpoints.py       # Integration tests for Flask API
```

## Setup

### 1. Install Test Dependencies

Activate your virtual environment and install testing dependencies:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

The testing dependencies include:
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities

### 2. Verify Installation

```bash
pytest --version
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Tests with Coverage

```bash
# Terminal coverage report
pytest --cov=. --cov-report=term

# HTML coverage report
pytest --cov=. --cov-report=html --cov-report=term

# View the HTML report
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

This will show:
- Which lines of code are covered by tests
- Coverage percentage for each module
- An HTML report in `htmlcov/` directory with detailed line-by-line coverage

### Run Specific Test Files

```bash
# Run only unit tests for models
pytest tests/test_models.py

# Run only integration tests
pytest tests/test_api_endpoints.py

# Run multiple specific files
pytest tests/test_models.py tests/test_db_models.py
```

### Run Tests by Marker

Tests are organized with markers for easy filtering:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests that don't require Ollama
pytest -m "not requires_ollama"
```

### Run Specific Test Classes or Functions

```bash
# Run a specific test class
pytest tests/test_models.py::TestSankeyNode

# Run a specific test function
pytest tests/test_models.py::TestSankeyNode::test_sankey_node_creation
```

## Test Markers

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests for API endpoints
- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.requires_ollama` - Tests requiring Ollama to be running

## Test Coverage

### Current Test Coverage

The test suite covers:

1. **Data Models** (models.py)
   - SankeyNode, BurndownDataPoint
   - VisualPayload factory methods
   - AssistantResponse serialization

2. **Database Models** (db_models.py)
   - User authentication and password hashing
   - FinancialProfile CRUD operations
   - BudgetPlan storage and retrieval
   - Model relationships

3. **Services**
   - **tools.py**: Tool definitions and execution
   - **llm_service.py**: LLM client and tool calling
   - **orchestrator.py**: Message processing and routing
   - **plan_generator.py**: Spending plan generation
   - **statement_analyzer.py**: Bank statement analysis

4. **API Endpoints** (app.py)
   - Authentication (register, login)
   - Onboarding
   - Plan generation and retrieval
   - Chat interface
   - Statement upload
   - Error handling and CORS

### View Detailed Coverage Report

After running tests with coverage:

```bash
# View in terminal
pytest --cov --cov-report=term-missing

# Generate and open HTML report
pytest --cov --cov-report=html
open htmlcov/index.html
```

## Writing New Tests

### Test File Naming

- Test files must start with `test_` or end with `_test.py`
- Test classes must start with `Test`
- Test functions must start with `test_`

### Using Fixtures

Common fixtures are defined in `conftest.py`:

```python
def test_example(client, sample_user):
    """Example test using fixtures."""
    # client: Flask test client
    # sample_user: Database user ID
    response = client.get(f"/get-plan/{sample_user}")
    assert response.status_code == 200
```

Available fixtures:
- `app` - Flask application instance
- `client` - Flask test client
- `sample_user` - User without profile
- `sample_user_with_profile` - User with complete profile
- `sample_plan_data` - Sample spending plan data
- `mock_llm_response` - Mock LLM response builder
- `sample_csv_content` - Sample CSV bank statement

### Mocking External Dependencies

Use `unittest.mock` or `pytest-mock` for mocking:

```python
from unittest.mock import patch, Mock

@patch('services.orchestrator.agent')
def test_with_mock(mock_agent):
    """Test with mocked LLM agent."""
    mock_agent.is_available.return_value = True
    mock_agent.chat.return_value = Mock(
        choices=[Mock(message=Mock(content="Response"))]
    )
    # Your test code here
```

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```bash
# Run tests with JUnit XML output for CI
pytest --junitxml=test-results.xml

# Run with coverage for CI reporting
pytest --cov --cov-report=xml
```

## Troubleshooting

### Tests Fail with Database Errors

The test suite uses an in-memory SQLite database. If you see database errors:

```bash
# Clear any cached Python files
find . -type d -name __pycache__ -exec rm -r {} +
find . -name "*.pyc" -delete

# Re-run tests
pytest
```

### Import Errors

Ensure you're in the correct directory and virtual environment:

```bash
cd BudgetBuddyBackend
source .venv/bin/activate
pytest
```

### Slow Tests

Some tests involving file I/O or mocking may be slower. To skip slow tests:

```bash
pytest -m "not slow"
```

### Tests Requiring Ollama

Tests marked with `requires_ollama` need Ollama running locally:

```bash
# Start Ollama (in another terminal)
ollama serve

# Run all tests including Ollama-dependent ones
pytest
```

To skip tests that need Ollama:

```bash
pytest -m "not requires_ollama"
```

## Test Maintenance

### Adding Tests for New Features

1. Create test file in `tests/` directory
2. Import the module to test
3. Write test class with descriptive name
4. Add appropriate markers (`@pytest.mark.unit`, etc.)
5. Use fixtures from `conftest.py` when possible
6. Run tests to verify

### Updating Fixtures

Shared test fixtures are in `conftest.py`. Update them when:
- Database schema changes
- New test data patterns emerge
- Mock responses need updates

## Coverage Goals

Target coverage goals:
- **Overall**: 80%+
- **Critical paths** (auth, data models): 90%+
- **API endpoints**: 85%+
- **Service logic**: 80%+

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Flask Testing Guide](https://flask.palletsprojects.com/en/latest/testing/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
