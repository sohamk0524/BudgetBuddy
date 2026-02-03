# BudgetBuddy Backend

Flask-based backend server for BudgetBuddy, providing AI-powered financial assistance.

## Quick Start

### 1. Setup Virtual Environment

```bash
# Create virtual environment (if not already created)
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Server

```bash
python app.py
```

The server will start on `http://localhost:5000`

## Running Tests

### Quick Test Commands

```bash
# Activate virtual environment first
source .venv/bin/activate

# Run all tests
pytest

# Run all tests with verbose output
pytest -v

# Run tests with coverage report
pytest --cov --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run specific test file
pytest tests/test_models.py
```

### View Coverage Report

After running tests with coverage:
```bash
open htmlcov/index.html
```

### Test Statistics

- **167 total test cases**
- **8 test modules** covering all backend components
- **Unit tests**: Data models, services, utilities
- **Integration tests**: API endpoints, database operations

For detailed testing documentation, see [tests/README.md](tests/README.md)

## Project Structure

```
BudgetBuddyBackend/
├── app.py                  # Flask application and API endpoints
├── models.py              # Data models (AssistantResponse, VisualPayload)
├── db_models.py           # Database models (User, FinancialProfile, BudgetPlan)
├── requirements.txt       # Python dependencies
├── pytest.ini            # Test configuration
├── services/             # Business logic
│   ├── orchestrator.py   # Main message processing
│   ├── plan_generator.py # Spending plan generation
│   ├── statement_analyzer.py # Bank statement analysis
│   ├── llm_service.py    # LLM wrapper (Ollama)
│   ├── tools.py          # AI agent tools
│   └── data_mock.py      # Mock data for development
└── tests/                # Test suite (see tests/README.md)
    ├── conftest.py       # Test fixtures
    ├── test_models.py
    ├── test_db_models.py
    ├── test_tools.py
    ├── test_llm_service.py
    ├── test_orchestrator.py
    ├── test_plan_generator.py
    ├── test_statement_analyzer.py
    └── test_api_endpoints.py
```

## API Endpoints

### Health & Info
- `GET /` - Welcome message
- `GET /health` - Health check

### Authentication
- `POST /register` - Register new user
- `POST /login` - User login

### User Profile
- `POST /onboarding` - Save financial profile

### Budget Planning
- `POST /generate-plan` - Generate spending plan
- `GET /get-plan/<user_id>` - Retrieve user's plan

### AI Interaction
- `POST /chat` - Chat with AI assistant
- `POST /upload-statement` - Upload bank statement for analysis

## Development

### Prerequisites
- Python 3.8+
- Ollama (optional, for LLM features)

### Running with Ollama

For full AI features, start Ollama in a separate terminal:
```bash
ollama serve
```

The backend will fall back to rule-based responses if Ollama is unavailable.

### Database

The application uses SQLite with SQLAlchemy ORM. The database file is automatically created at `instance/budgetbuddy.db` on first run.

## Testing Notes

- Tests use an in-memory SQLite database (no persistent state)
- LLM service is mocked in tests (Ollama not required)
- Tests marked with `@pytest.mark.requires_ollama` need Ollama running
- All tests are designed to run independently

See [tests/README.md](tests/README.md) for comprehensive testing documentation.
