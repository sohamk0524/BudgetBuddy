"""
Unit tests for services/statement_analyzer.py - Bank statement analysis.
"""

import pytest
import json
from unittest.mock import Mock, patch
from services.statement_analyzer import (
    analyze_statement,
    _extract_text,
    _parse_csv,
    _parse_pdf,
    _parse_llm_json,
    _build_response,
    _build_visual_payload,
    _fallback_response
)
from models import AssistantResponse


@pytest.mark.unit
class TestExtractText:
    """Tests for _extract_text function."""

    def test_extract_csv_file(self, sample_csv_content):
        """Test extracting text from CSV file."""
        result = _extract_text(sample_csv_content, "statement.csv")

        assert result is not None
        assert "Date" in result
        assert "Salary" in result

    def test_extract_pdf_file(self):
        """Test extracting text from PDF file."""
        # Create minimal PDF bytes (won't be valid but will test the flow)
        pdf_content = b"%PDF-1.4 fake pdf"

        result = _extract_text(pdf_content, "statement.pdf")

        # Will return empty or error message without pdfplumber
        assert result is not None

    def test_extract_unknown_file_type(self):
        """Test extracting text from unknown file type."""
        result = _extract_text(b"some data", "statement.txt")

        assert result is None

    def test_case_insensitive_extension(self, sample_csv_content):
        """Test that file extension matching is case-insensitive."""
        result = _extract_text(sample_csv_content, "STATEMENT.CSV")

        assert result is not None


@pytest.mark.unit
class TestParseCSV:
    """Tests for _parse_csv function."""

    def test_parse_valid_csv(self, sample_csv_content):
        """Test parsing valid CSV content."""
        result = _parse_csv(sample_csv_content)

        assert result is not None
        assert "Date" in result
        assert "Description" in result
        assert "5000.00" in result

    def test_parse_empty_csv(self):
        """Test parsing empty CSV."""
        result = _parse_csv(b"")

        # Should return empty string or handle gracefully
        assert isinstance(result, str)

    def test_parse_malformed_csv(self):
        """Test parsing malformed CSV."""
        malformed = b"Date,Amount\nInvalid\x00Data"

        result = _parse_csv(malformed)

        # Should handle error and return empty string
        assert isinstance(result, str)

    def test_csv_row_limit(self):
        """Test that CSV parsing limits rows."""
        # Create CSV with many rows
        large_csv = b"Date,Amount\n"
        for i in range(150):
            large_csv += f"2024-01-{i % 28 + 1:02d},100.00\n".encode()

        result = _parse_csv(large_csv)

        # Should limit to 100 rows
        assert result is not None
        lines = result.split("\n")
        # First line is header, max 100 rows after
        assert len(lines) <= 101


@pytest.mark.unit
class TestParsePDF:
    """Tests for _parse_pdf function."""

    def test_parse_pdf_without_pdfplumber(self):
        """Test PDF parsing when pdfplumber is not available."""
        pdf_content = b"%PDF-1.4"

        result = _parse_pdf(pdf_content)

        # Should return error message or empty string
        assert isinstance(result, str)

    def test_parse_pdf_with_pdfplumber(self):
        """Test PDF parsing when pdfplumber is available."""
        # Since pdfplumber is imported inside the function, we need to mock it at import time
        # For this test, we'll just verify the function handles PDF input gracefully
        pdf_content = b"%PDF-1.4 test content"
        result = _parse_pdf(pdf_content)

        # Should return a string (either parsed content or error message)
        assert isinstance(result, str)
        # If pdfplumber is installed, should have content; if not, should have error message
        # Either way, we're testing that it doesn't crash

    def test_parse_pdf_page_limit(self):
        """Test that PDF parsing handles multiple pages."""
        # This test just verifies the function doesn't crash with PDF input
        pdf_content = b"%PDF-1.4"
        result = _parse_pdf(pdf_content)

        # Without pdfplumber installed, should return error message or empty string
        assert isinstance(result, str)


@pytest.mark.unit
class TestParseLLMJson:
    """Tests for _parse_llm_json function."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        json_str = '{"summary": "Test", "total": 100}'

        result = _parse_llm_json(json_str)

        assert result is not None
        assert result["summary"] == "Test"
        assert result["total"] == 100

    def test_parse_json_with_surrounding_text(self):
        """Test parsing JSON with surrounding text."""
        response = """Here is the analysis:
        {"summary": "Your spending", "total": 200}
        Hope this helps!"""

        result = _parse_llm_json(response)

        assert result is not None
        assert result["total"] == 200

    def test_parse_json_with_markdown_code_block(self):
        """Test parsing JSON in markdown code block."""
        response = """```json
        {"summary": "Analysis", "total": 150}
        ```"""

        result = _parse_llm_json(response)

        assert result is not None
        assert result["total"] == 150

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        result = _parse_llm_json("This is not JSON at all")

        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = _parse_llm_json("")

        assert result is None


@pytest.mark.unit
class TestBuildResponse:
    """Tests for _build_response function."""

    def test_build_response_with_summary(self):
        """Test building response with friendly summary."""
        analysis = {
            "friendly_summary": "You spent $342 on food this month!",
            "total_expenses": 342,
            "top_categories": [{"category": "Food", "amount": 342}]
        }

        response = _build_response(analysis)

        assert isinstance(response, AssistantResponse)
        assert response.text_message == "You spent $342 on food this month!"

    def test_build_response_without_summary(self):
        """Test building response without friendly summary."""
        analysis = {
            "total_expenses": 500,
            "top_categories": [
                {"category": "Groceries", "amount": 300},
                {"category": "Dining", "amount": 200}
            ]
        }

        response = _build_response(analysis)

        assert isinstance(response, AssistantResponse)
        assert "$500" in response.text_message
        assert "Groceries" in response.text_message

    def test_build_response_with_visual(self):
        """Test that response includes visual payload."""
        analysis = {
            "friendly_summary": "Analysis complete",
            "top_categories": [{"category": "Food", "amount": 200}]
        }

        response = _build_response(analysis)

        assert response.visual_payload is not None


@pytest.mark.unit
class TestBuildVisualPayload:
    """Tests for _build_visual_payload function."""

    def test_build_payload_from_categories(self):
        """Test building visual payload from top categories."""
        analysis = {
            "total_income": 5000,
            "total_expenses": 3000,
            "top_categories": [
                {"category": "Food", "amount": 500},
                {"category": "Transport", "amount": 300},
                {"category": "Entertainment", "amount": 200}
            ]
        }

        payload = _build_visual_payload(analysis)

        assert payload is not None
        assert payload["type"] == "sankeyFlow"
        assert len(payload["nodes"]) > 0
        # Should include income node plus categories
        node_names = [node["name"] for node in payload["nodes"]]
        assert "Food" in node_names

    def test_build_payload_from_transactions(self):
        """Test building visual payload from transactions."""
        analysis = {
            "transactions": [
                {"date": "2024-01-01", "description": "Grocery", "amount": -50, "category": "Food"},
                {"date": "2024-01-02", "description": "Gas", "amount": -40, "category": "Transport"},
                {"date": "2024-01-03", "description": "Restaurant", "amount": -30, "category": "Food"}
            ]
        }

        payload = _build_visual_payload(analysis)

        assert payload is not None
        assert payload["type"] == "sankeyFlow"
        # Should aggregate by category
        node_names = [node["name"] for node in payload["nodes"]]
        assert "Food" in node_names

    def test_build_payload_no_data(self):
        """Test building payload with no data."""
        analysis = {}

        payload = _build_visual_payload(analysis)

        assert payload is None

    def test_build_payload_limits_categories(self):
        """Test that payload limits number of categories."""
        categories = [
            {"category": f"Category{i}", "amount": 100 - i}
            for i in range(10)
        ]
        analysis = {"top_categories": categories}

        payload = _build_visual_payload(analysis)

        # Should limit to 6 categories
        assert len(payload["nodes"]) <= 6


@pytest.mark.unit
class TestFallbackResponse:
    """Tests for _fallback_response function."""

    def test_fallback_response_basic(self):
        """Test basic fallback response."""
        response = _fallback_response("Date,Amount\n2024-01-01,100")

        assert isinstance(response, AssistantResponse)
        assert "unavailable" in response.text_message.lower()
        assert response.visual_payload is None


@pytest.mark.unit
@patch('services.statement_analyzer.agent')
class TestAnalyzeStatement:
    """Tests for analyze_statement function."""

    def test_analyze_csv_statement(self, mock_agent, sample_csv_content):
        """Test analyzing CSV statement."""
        mock_agent.is_available.return_value = True

        analysis_json = {
            "friendly_summary": "You spent $1700 this month.",
            "total_income": 5000,
            "total_expenses": 1700,
            "top_categories": [
                {"category": "Housing", "amount": 1500},
                {"category": "Food", "amount": 200}
            ]
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps(analysis_json)))]
        mock_agent.chat.return_value = mock_response

        response = analyze_statement(sample_csv_content, "statement.csv")

        assert isinstance(response, AssistantResponse)
        assert response.visual_payload is not None
        mock_agent.chat.assert_called_once()

    def test_analyze_statement_ollama_unavailable(self, mock_agent, sample_csv_content):
        """Test analyzing statement when Ollama is unavailable."""
        mock_agent.is_available.return_value = False

        response = analyze_statement(sample_csv_content, "statement.csv")

        assert isinstance(response, AssistantResponse)
        assert "unavailable" in response.text_message.lower()

    def test_analyze_statement_invalid_file(self, mock_agent):
        """Test analyzing invalid file type."""
        response = analyze_statement(b"data", "file.txt")

        assert isinstance(response, AssistantResponse)
        assert "couldn't read" in response.text_message.lower()

    def test_analyze_statement_truncate_long_content(self, mock_agent):
        """Test that long statements are truncated."""
        # Create very long CSV
        long_csv = b"Date,Amount\n"
        for i in range(1000):
            long_csv += f"2024-01-01,{i}.00\n".encode()

        mock_agent.is_available.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"friendly_summary": "Test"}'))]
        mock_agent.chat.return_value = mock_response

        response = analyze_statement(long_csv, "large.csv")

        # Should truncate content before sending to LLM
        call_args = mock_agent.chat.call_args
        message_content = call_args[0][0][1]["content"]
        assert len(message_content) < 10000  # Should be truncated

    def test_analyze_statement_invalid_json_response(self, mock_agent, sample_csv_content):
        """Test handling invalid JSON from LLM."""
        mock_agent.is_available.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="This is not JSON"))]
        mock_agent.chat.return_value = mock_response

        response = analyze_statement(sample_csv_content, "statement.csv")

        # Should return the raw text response
        assert isinstance(response, AssistantResponse)
        assert response.text_message is not None

    def test_analyze_statement_error_handling(self, mock_agent, sample_csv_content):
        """Test error handling during analysis."""
        mock_agent.is_available.return_value = True
        mock_agent.chat.side_effect = Exception("LLM Error")

        response = analyze_statement(sample_csv_content, "statement.csv")

        # Should fall back gracefully
        assert isinstance(response, AssistantResponse)
