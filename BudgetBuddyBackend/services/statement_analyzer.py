"""
Statement Analyzer Service - Parses and analyzes bank statements.

This module uses a hybrid approach:
1. Custom parsing logic extracts financial data (balances, transactions, totals)
2. LLM provides categorization and friendly summaries
"""

import csv
import io
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from models import AssistantResponse, VisualPayload, SankeyNode
from services.llm_service import Agent

# Statement analysis agent
analysis_agent = Agent(
    name="StatementAnalyzer",
    instructions="""You are BudgetBuddy, a friendly financial assistant helping college students understand their spending.

Analyze bank statements and provide helpful, conversational insights. Be encouraging and non-judgmental.""",
    model="claude-opus-4-6",
)

USER_PROMPT_TEMPLATE = """Here is a bank statement to analyze:

<BEGIN_STATEMENT>
{statement_text}
<END_STATEMENT>

I've already extracted these numbers from the statement:
- Ending Balance: ${ending_balance:.2f}
- Total Deposits: ${total_income:.2f}
- Total Withdrawals: ${total_expenses:.2f}
- Number of transactions: {transaction_count}

Please provide:
1. A friendly 2-3 sentence summary mentioning the key numbers
2. Categorize the spending into categories like Food, Transportation, Shopping, Bills, Entertainment, etc.

Respond with JSON:
{{
  "friendly_summary": "Your conversational summary here...",
  "top_categories": [
    {{"category": "Food", "amount": 0.00}},
    {{"category": "Shopping", "amount": 0.00}}
  ]
}}

Return valid JSON only."""


def analyze_statement(file_content: bytes, filename: str, return_analysis: bool = False):
    """
    Analyze a bank statement file using hybrid parsing.

    Args:
        file_content: Raw bytes of the uploaded file
        filename: Original filename (used to detect type)
        return_analysis: If True, return tuple of (response, analysis_dict)

    Returns:
        If return_analysis is False: AssistantResponse
        If return_analysis is True: Tuple of (AssistantResponse, dict or None)
    """
    # Step 1: Parse statement data using custom logic
    parsed_data = parse_statement_data(file_content, filename)

    if not parsed_data:
        response = AssistantResponse(
            text_message="I couldn't read that file. Please upload a PDF or CSV bank statement.",
            visual_payload=None
        )
        return (response, None) if return_analysis else response

    print(f"Parsed statement data: balance={parsed_data.get('ending_balance')}, "
          f"income={parsed_data.get('total_income')}, expenses={parsed_data.get('total_expenses')}")

    # Step 2: Try to get LLM categorization and summary
    llm_analysis = _get_llm_analysis(parsed_data)

    # Step 3: Merge parsed data with LLM analysis
    final_analysis = _merge_analysis(parsed_data, llm_analysis)

    # Step 4: Build response
    response = _build_response(final_analysis)

    return (response, final_analysis) if return_analysis else response


def parse_statement_data(file_content: bytes, filename: str) -> Optional[Dict[str, Any]]:
    """
    Parse financial data from a bank statement file.

    Returns a dict with:
    - ending_balance: float
    - beginning_balance: float (if found)
    - total_income: float (deposits/credits)
    - total_expenses: float (withdrawals/debits)
    - transactions: list of transaction dicts
    - statement_start_date: str (YYYY-MM-DD)
    - statement_end_date: str (YYYY-MM-DD)
    - raw_text: str (for LLM analysis)
    """
    filename_lower = filename.lower()

    if filename_lower.endswith(".csv"):
        return _parse_csv_statement(file_content)
    elif filename_lower.endswith(".pdf"):
        return _parse_pdf_statement(file_content)
    else:
        return None


def _parse_csv_statement(file_content: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse a CSV bank statement.

    Handles common CSV formats:
    - Date, Description, Amount, Balance
    - Date, Description, Debit, Credit, Balance
    - Transaction Date, Post Date, Description, Category, Type, Amount
    """
    try:
        # Try different encodings
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                text_content = file_content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return None

        # Parse CSV
        reader = csv.reader(io.StringIO(text_content))
        rows = list(reader)

        if len(rows) < 2:
            return None

        # Detect column structure from header
        header = [col.lower().strip() for col in rows[0]]
        col_map = _detect_csv_columns(header)

        if not col_map:
            # Try without header (first row might be data)
            col_map = _detect_csv_columns_from_data(rows)

        # Extract transactions
        transactions = []
        total_income = 0.0
        total_expenses = 0.0
        balances = []
        dates = []

        data_rows = rows[1:] if col_map.get('has_header', True) else rows

        for row in data_rows:
            if len(row) < 2:
                continue

            tx = _parse_csv_row(row, col_map)
            if tx:
                transactions.append(tx)

                amount = tx.get('amount', 0)
                if amount > 0:
                    total_income += amount
                else:
                    total_expenses += abs(amount)

                if tx.get('balance') is not None:
                    balances.append(tx['balance'])

                if tx.get('date'):
                    dates.append(tx['date'])

        # Determine ending balance
        ending_balance = balances[-1] if balances else (total_income - total_expenses)
        beginning_balance = balances[0] if balances else None

        # Build raw text for LLM
        raw_text = "\n".join([" | ".join(row) for row in rows[:50]])

        return {
            'ending_balance': ending_balance,
            'beginning_balance': beginning_balance,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'transactions': transactions,
            'statement_start_date': min(dates) if dates else None,
            'statement_end_date': max(dates) if dates else None,
            'raw_text': raw_text
        }

    except Exception as e:
        print(f"CSV parse error: {e}")
        return None


def _detect_csv_columns(header: List[str]) -> Optional[Dict[str, int]]:
    """Detect column indices from header row."""
    col_map = {'has_header': True}

    for i, col in enumerate(header):
        col_clean = col.lower().strip()

        # Date column
        if any(term in col_clean for term in ['date', 'posted', 'trans']):
            if 'date_col' not in col_map:
                col_map['date_col'] = i

        # Description column
        if any(term in col_clean for term in ['description', 'desc', 'memo', 'narrative', 'details', 'payee']):
            col_map['desc_col'] = i

        # Amount column (single column for +/-)
        if col_clean in ['amount', 'amt', 'transaction amount', 'value']:
            col_map['amount_col'] = i

        # Debit column (expenses)
        if any(term in col_clean for term in ['debit', 'withdrawal', 'out', 'expense']):
            col_map['debit_col'] = i

        # Credit column (income)
        if any(term in col_clean for term in ['credit', 'deposit', 'in', 'income']):
            col_map['credit_col'] = i

        # Balance column
        if any(term in col_clean for term in ['balance', 'running', 'total']):
            col_map['balance_col'] = i

        # Category column
        if any(term in col_clean for term in ['category', 'type', 'class']):
            col_map['category_col'] = i

    # Need at least date and some amount column
    if 'date_col' in col_map and ('amount_col' in col_map or 'debit_col' in col_map):
        return col_map

    return None


def _detect_csv_columns_from_data(rows: List[List[str]]) -> Optional[Dict[str, int]]:
    """Try to detect columns by analyzing data patterns."""
    if len(rows) < 3:
        return None

    col_map = {'has_header': False}

    # Analyze first few data rows
    for col_idx in range(min(10, len(rows[0]))):
        date_count = 0
        amount_count = 0

        for row in rows[:10]:
            if col_idx >= len(row):
                continue
            val = row[col_idx].strip()

            # Check if it looks like a date
            if _parse_date(val):
                date_count += 1

            # Check if it looks like an amount
            if _parse_amount(val) is not None:
                amount_count += 1

        if date_count >= 3 and 'date_col' not in col_map:
            col_map['date_col'] = col_idx

        if amount_count >= 3 and 'amount_col' not in col_map:
            col_map['amount_col'] = col_idx

    if 'date_col' in col_map and 'amount_col' in col_map:
        return col_map

    return None


def _parse_csv_row(row: List[str], col_map: Dict[str, int]) -> Optional[Dict[str, Any]]:
    """Parse a single CSV row into a transaction dict."""
    try:
        tx = {}

        # Date
        if 'date_col' in col_map and col_map['date_col'] < len(row):
            tx['date'] = _parse_date(row[col_map['date_col']])

        # Description
        if 'desc_col' in col_map and col_map['desc_col'] < len(row):
            tx['description'] = row[col_map['desc_col']].strip()
        else:
            # Try to find description in other columns
            for i, val in enumerate(row):
                if i not in [col_map.get('date_col'), col_map.get('amount_col'),
                            col_map.get('debit_col'), col_map.get('credit_col'),
                            col_map.get('balance_col')]:
                    if len(val.strip()) > 3 and not _parse_amount(val):
                        tx['description'] = val.strip()
                        break

        # Amount - handle different formats
        if 'amount_col' in col_map and col_map['amount_col'] < len(row):
            amount = _parse_amount(row[col_map['amount_col']])
            if amount is not None:
                tx['amount'] = amount
        elif 'debit_col' in col_map or 'credit_col' in col_map:
            debit = 0.0
            credit = 0.0
            if 'debit_col' in col_map and col_map['debit_col'] < len(row):
                debit = _parse_amount(row[col_map['debit_col']]) or 0.0
            if 'credit_col' in col_map and col_map['credit_col'] < len(row):
                credit = _parse_amount(row[col_map['credit_col']]) or 0.0
            tx['amount'] = credit - abs(debit)

        # Balance
        if 'balance_col' in col_map and col_map['balance_col'] < len(row):
            balance = _parse_amount(row[col_map['balance_col']])
            if balance is not None:
                tx['balance'] = balance

        # Category
        if 'category_col' in col_map and col_map['category_col'] < len(row):
            tx['category'] = row[col_map['category_col']].strip()

        if 'amount' in tx or 'balance' in tx:
            return tx
        return None

    except Exception as e:
        print(f"Row parse error: {e}")
        return None


def _parse_pdf_statement(file_content: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse a PDF bank statement.

    Extracts:
    - Balance summaries using regex patterns
    - Transaction tables
    - Date ranges
    """
    try:
        import pdfplumber
    except ImportError:
        print("pdfplumber not installed. Install with: pip install pdfplumber")
        return None

    try:
        text_parts = []
        all_tables = []

        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages[:15]:  # Limit pages
                # Extract text
                text = page.extract_text()
                if text:
                    text_parts.append(text)

                # Extract tables
                tables = page.extract_tables()
                all_tables.extend(tables)

        full_text = "\n\n".join(text_parts)

        if not full_text.strip():
            return None

        # Extract financial data using regex patterns
        data = _extract_financial_data_from_text(full_text)

        # Try to get additional data from tables
        table_data = _extract_data_from_tables(all_tables)

        # Merge table data with text data
        if table_data:
            if not data.get('transactions'):
                data['transactions'] = table_data.get('transactions', [])
            if not data.get('total_income') and table_data.get('total_income'):
                data['total_income'] = table_data['total_income']
            if not data.get('total_expenses') and table_data.get('total_expenses'):
                data['total_expenses'] = table_data['total_expenses']

        # Calculate totals from transactions if not found
        if data.get('transactions') and not data.get('total_income'):
            income = sum(t.get('amount', 0) for t in data['transactions'] if t.get('amount', 0) > 0)
            expenses = sum(abs(t.get('amount', 0)) for t in data['transactions'] if t.get('amount', 0) < 0)
            data['total_income'] = income
            data['total_expenses'] = expenses

        # If no ending balance found, estimate from transactions
        if not data.get('ending_balance') and data.get('transactions'):
            data['ending_balance'] = data.get('total_income', 0) - data.get('total_expenses', 0)

        data['raw_text'] = full_text[:8000]

        return data

    except Exception as e:
        print(f"PDF parse error: {e}")
        return None


def _extract_financial_data_from_text(text: str) -> Dict[str, Any]:
    """
    Extract financial data from statement text using regex patterns.

    Handles various bank statement formats.
    """
    data = {
        'ending_balance': None,
        'beginning_balance': None,
        'total_income': None,
        'total_expenses': None,
        'transactions': [],
        'statement_start_date': None,
        'statement_end_date': None
    }

    # Patterns for ending balance (most important for net worth)
    ending_balance_patterns = [
        r'ending\s+balance[:\s]*\$?([\d,]+\.?\d*)',
        r'closing\s+balance[:\s]*\$?([\d,]+\.?\d*)',
        r'new\s+balance[:\s]*\$?([\d,]+\.?\d*)',
        r'current\s+balance[:\s]*\$?([\d,]+\.?\d*)',
        r'available\s+balance[:\s]*\$?([\d,]+\.?\d*)',
        r'balance\s+as\s+of[^$]*\$?([\d,]+\.?\d*)',
        r'account\s+balance[:\s]*\$?([\d,]+\.?\d*)',
        r'total\s+balance[:\s]*\$?([\d,]+\.?\d*)',
    ]

    for pattern in ending_balance_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['ending_balance'] = _parse_amount(match.group(1))
            if data['ending_balance']:
                print(f"Found ending balance: {data['ending_balance']} (pattern: {pattern})")
                break

    # Patterns for beginning balance
    beginning_balance_patterns = [
        r'beginning\s+balance[:\s]*\$?([\d,]+\.?\d*)',
        r'opening\s+balance[:\s]*\$?([\d,]+\.?\d*)',
        r'previous\s+balance[:\s]*\$?([\d,]+\.?\d*)',
        r'starting\s+balance[:\s]*\$?([\d,]+\.?\d*)',
    ]

    for pattern in beginning_balance_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['beginning_balance'] = _parse_amount(match.group(1))
            if data['beginning_balance']:
                break

    # Patterns for total deposits/income
    income_patterns = [
        r'total\s+deposits[:\s]*\$?([\d,]+\.?\d*)',
        r'total\s+credits[:\s]*\$?([\d,]+\.?\d*)',
        r'deposits[:\s]+\$?([\d,]+\.?\d*)',
        r'total\s+additions[:\s]*\$?([\d,]+\.?\d*)',
        r'money\s+in[:\s]*\$?([\d,]+\.?\d*)',
    ]

    for pattern in income_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['total_income'] = _parse_amount(match.group(1))
            if data['total_income']:
                break

    # Patterns for total withdrawals/expenses
    expense_patterns = [
        r'total\s+withdrawals[:\s]*\$?([\d,]+\.?\d*)',
        r'total\s+debits[:\s]*\$?([\d,]+\.?\d*)',
        r'withdrawals[:\s]+\$?([\d,]+\.?\d*)',
        r'total\s+subtractions[:\s]*\$?([\d,]+\.?\d*)',
        r'money\s+out[:\s]*\$?([\d,]+\.?\d*)',
        r'total\s+payments[:\s]*\$?([\d,]+\.?\d*)',
    ]

    for pattern in expense_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['total_expenses'] = _parse_amount(match.group(1))
            if data['total_expenses']:
                break

    # Try to extract statement date range
    date_range_patterns = [
        r'statement\s+period[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|-|through)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|-|through)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'from\s+(\w+\s+\d{1,2},?\s+\d{4})\s+to\s+(\w+\s+\d{1,2},?\s+\d{4})',
    ]

    for pattern in date_range_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start_date = _parse_date(match.group(1))
            end_date = _parse_date(match.group(2))
            if start_date:
                data['statement_start_date'] = start_date
            if end_date:
                data['statement_end_date'] = end_date
            break

    # Extract individual transactions
    data['transactions'] = _extract_transactions_from_text(text)

    return data


def _extract_transactions_from_text(text: str) -> List[Dict[str, Any]]:
    """Extract individual transactions from statement text."""
    transactions = []

    # Pattern for transaction lines (date, description, amount)
    # Matches: MM/DD/YYYY or MM/DD/YY followed by description and amount
    tx_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+(-?\$?[\d,]+\.?\d*)\s*$'

    for line in text.split('\n'):
        line = line.strip()
        match = re.match(tx_pattern, line)
        if match:
            date_str = match.group(1)
            desc = match.group(2).strip()
            amount_str = match.group(3)

            date = _parse_date(date_str)
            amount = _parse_amount(amount_str)

            if date and amount is not None:
                transactions.append({
                    'date': date,
                    'description': desc,
                    'amount': amount
                })

    return transactions


def _extract_data_from_tables(tables: List[List[List[str]]]) -> Optional[Dict[str, Any]]:
    """Extract financial data from PDF tables."""
    if not tables:
        return None

    transactions = []
    total_income = 0.0
    total_expenses = 0.0

    for table in tables:
        if not table or len(table) < 2:
            continue

        # Try to detect column structure
        header = table[0] if table else []
        col_map = _detect_csv_columns([str(c).lower() if c else '' for c in header])

        if col_map:
            for row in table[1:]:
                row_str = [str(c) if c else '' for c in row]
                tx = _parse_csv_row(row_str, col_map)
                if tx:
                    transactions.append(tx)
                    amount = tx.get('amount', 0)
                    if amount > 0:
                        total_income += amount
                    else:
                        total_expenses += abs(amount)

    if transactions:
        return {
            'transactions': transactions,
            'total_income': total_income,
            'total_expenses': total_expenses
        }

    return None


def _parse_amount(value: str) -> Optional[float]:
    """
    Parse an amount string into a float.

    Handles:
    - $1,234.56
    - 1234.56
    - (123.45) for negative
    - -123.45
    - 123.45 CR/DR
    """
    if not value or not isinstance(value, str):
        return None

    value = value.strip()
    if not value:
        return None

    # Check for negative indicators
    is_negative = False
    if value.startswith('(') and value.endswith(')'):
        is_negative = True
        value = value[1:-1]
    elif value.startswith('-'):
        is_negative = True
        value = value[1:]
    elif value.upper().endswith('DR') or value.upper().endswith('DEBIT'):
        is_negative = True
        value = re.sub(r'\s*(DR|DEBIT)\s*$', '', value, flags=re.IGNORECASE)

    # Remove currency symbols and commas
    value = re.sub(r'[$,\s]', '', value)

    # Remove CR/Credit suffix
    value = re.sub(r'\s*(CR|CREDIT)\s*$', '', value, flags=re.IGNORECASE)

    try:
        amount = float(value)
        return -amount if is_negative else amount
    except ValueError:
        return None


def _parse_date(value: str) -> Optional[str]:
    """
    Parse a date string into YYYY-MM-DD format.

    Handles:
    - MM/DD/YYYY, MM-DD-YYYY
    - MM/DD/YY, MM-DD-YY
    - YYYY-MM-DD
    - Month DD, YYYY
    """
    if not value or not isinstance(value, str):
        return None

    value = value.strip()

    formats = [
        '%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y',
        '%Y-%m-%d', '%Y/%m/%d',
        '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
        '%B %d, %Y', '%b %d, %Y', '%B %d %Y', '%b %d %Y',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue

    return None


def _get_llm_analysis(parsed_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get LLM analysis for categorization and summary."""
    try:
        if not analysis_agent.is_available():
            print("LLM not available - check ANTHROPIC_API_KEY")
            return None

        raw_text = parsed_data.get('raw_text', '')
        if not raw_text:
            return None

        # Truncate for LLM context
        if len(raw_text) > 6000:
            raw_text = raw_text[:6000] + "\n...[truncated]..."

        prompt = USER_PROMPT_TEMPLATE.format(
            statement_text=raw_text,
            ending_balance=parsed_data.get('ending_balance', 0) or 0,
            total_income=parsed_data.get('total_income', 0) or 0,
            total_expenses=parsed_data.get('total_expenses', 0) or 0,
            transaction_count=len(parsed_data.get('transactions', []))
        )

        result = analysis_agent.run(prompt)
        content = result.get("content", "")

        return _parse_llm_json(content)

    except Exception as e:
        print(f"LLM analysis error: {e}")
        return None


def _parse_llm_json(content: str) -> Optional[Dict[str, Any]]:
    """Try to extract JSON from LLM response."""
    # Try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown code fence
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try to find JSON object in response
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(content[start:end])
    except json.JSONDecodeError:
        pass

    return None


def _merge_analysis(parsed_data: Dict[str, Any], llm_analysis: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge parsed data with LLM analysis."""
    result = {
        'ending_balance': parsed_data.get('ending_balance', 0) or 0,
        'beginning_balance': parsed_data.get('beginning_balance'),
        'total_income': parsed_data.get('total_income', 0) or 0,
        'total_expenses': parsed_data.get('total_expenses', 0) or 0,
        'transactions': parsed_data.get('transactions', []),
        'statement_start_date': parsed_data.get('statement_start_date'),
        'statement_end_date': parsed_data.get('statement_end_date'),
    }

    # Add LLM analysis if available
    if llm_analysis:
        result['friendly_summary'] = llm_analysis.get('friendly_summary', '')
        result['top_categories'] = llm_analysis.get('top_categories', [])
    else:
        # Generate basic summary without LLM
        result['friendly_summary'] = _generate_basic_summary(result)
        result['top_categories'] = _categorize_transactions_basic(result.get('transactions', []))

    # Store metadata for the LLM analysis field
    result['metadata'] = {
        'ending_balance': result['ending_balance'],
        'total_income': result['total_income'],
        'total_expenses': result['total_expenses']
    }

    return result


def _generate_basic_summary(data: Dict[str, Any]) -> str:
    """Generate a basic summary when LLM is not available."""
    balance = data.get('ending_balance', 0)
    income = data.get('total_income', 0)
    expenses = data.get('total_expenses', 0)
    tx_count = len(data.get('transactions', []))

    if balance and expenses:
        return f"Your statement shows an ending balance of ${balance:,.2f}. You had ${income:,.2f} in deposits and ${expenses:,.2f} in withdrawals across {tx_count} transactions."
    elif expenses:
        return f"I found ${expenses:,.2f} in total spending across {tx_count} transactions."
    else:
        return "I've processed your statement. Check the breakdown below for details."


def _categorize_transactions_basic(transactions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Basic transaction categorization without LLM."""
    category_keywords = {
        'Food': ['restaurant', 'food', 'grocery', 'uber eats', 'doordash', 'grubhub', 'coffee', 'starbucks', 'mcdonald', 'chipotle', 'pizza'],
        'Transportation': ['uber', 'lyft', 'gas', 'shell', 'chevron', 'parking', 'transit', 'metro'],
        'Shopping': ['amazon', 'target', 'walmart', 'costco', 'best buy', 'apple', 'shop'],
        'Entertainment': ['netflix', 'spotify', 'hulu', 'movie', 'game', 'steam'],
        'Bills': ['electric', 'water', 'internet', 'phone', 'insurance', 'rent', 'utility'],
        'Transfer': ['transfer', 'venmo', 'zelle', 'paypal', 'cash app'],
    }

    category_totals = {}

    for tx in transactions:
        desc = (tx.get('description', '') or '').lower()
        amount = tx.get('amount', 0)

        if amount >= 0:  # Skip income
            continue

        category = 'Other'
        for cat, keywords in category_keywords.items():
            if any(kw in desc for kw in keywords):
                category = cat
                break

        category_totals[category] = category_totals.get(category, 0) + abs(amount)

    # Sort by amount and return top categories
    sorted_cats = sorted(category_totals.items(), key=lambda x: -x[1])
    return [{'category': cat, 'amount': round(amt, 2)} for cat, amt in sorted_cats[:6]]


def _build_response(analysis: Dict[str, Any]) -> AssistantResponse:
    """Build AssistantResponse from merged analysis."""
    friendly_summary = analysis.get('friendly_summary', '')

    if not friendly_summary:
        friendly_summary = _generate_basic_summary(analysis)

    visual_payload = _build_visual_payload(analysis)

    return AssistantResponse(
        text_message=friendly_summary,
        visual_payload=visual_payload
    )


def _build_visual_payload(analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build a visual payload from the analysis."""
    top_categories = analysis.get('top_categories', [])
    total_income = analysis.get('total_income', 0)

    if top_categories:
        nodes = []
        if total_income:
            nodes.append(SankeyNode(id="income", name="Income", value=float(total_income)))

        for cat in top_categories[:6]:
            cat_name = cat.get('category', 'Other')
            cat_amount = cat.get('amount', 0)
            if isinstance(cat_amount, str):
                cat_amount = _parse_amount(cat_amount) or 0
            if cat_amount > 0:
                nodes.append(SankeyNode(
                    id=cat_name.lower().replace(" ", "_"),
                    name=cat_name,
                    value=round(float(cat_amount), 2)
                ))

        if nodes:
            return VisualPayload.sankey_flow(nodes)

    return None
