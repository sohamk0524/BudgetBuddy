"""
Statement Parser Tool - Parse and analyze bank statements with enhanced features.
"""

import json
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict

from tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolContext,
    ToolResult,
    ToolCategory,
)
from models import VisualPayload, SankeyNode


class ParseBankStatementTool(Tool):
    """Tool for parsing and analyzing bank statements with enhanced features."""

    definition = ToolDefinition(
        name="parse_bank_statement",
        display_name="Bank Statement Analyzer",
        category=ToolCategory.DOCUMENT_PROCESSING,
        version="2.0.0",

        description="Parse an uploaded bank statement (PDF or CSV) and extract transaction data, balances, spending patterns, and insights.",

        when_to_use="Use when the user has uploaded a bank statement file and wants it analyzed. Also use when they ask about their uploaded statement data.",

        when_not_to_use="Do not use for general spending questions without a recent upload, or for hypothetical scenarios.",

        example_triggers=[
            "analyze my bank statement",
            "what does my statement show",
            "parse this file",
            "show my transactions",
            "what did I spend on",
        ],

        parameters=[
            ToolParameter(
                name="file_id",
                type="string",
                description="The ID of the uploaded file to analyze (optional if file was just uploaded)",
                required=False
            ),
            ToolParameter(
                name="analysis_depth",
                type="string",
                description="Level of analysis: 'quick' for summary, 'detailed' for full breakdown with insights",
                required=False,
                default="detailed",
                enum=["quick", "detailed"]
            ),
            ToolParameter(
                name="detect_recurring",
                type="boolean",
                description="Whether to identify recurring transactions (subscriptions, bills)",
                required=False,
                default=True
            ),
            ToolParameter(
                name="detect_anomalies",
                type="boolean",
                description="Whether to flag unusual transactions",
                required=False,
                default=True
            ),
        ],

        requires=["authenticated"],
        produces=["data:transactions", "data:spending_summary", "visual:categoryBreakdown"],
        side_effects=["updates_saved_statement"],
        confirmation_required=False,
        is_destructive=False,
        timeout_seconds=60,
        visual_type="sankeyFlow",
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Execute the statement parsing and analysis."""
        try:
            from db_models import db, SavedStatement, Transaction
            from services.statement_analyzer import analyze_statement

            analysis_depth = context.params.get("analysis_depth", "detailed")
            detect_recurring = context.params.get("detect_recurring", True)
            detect_anomalies = context.params.get("detect_anomalies", True)

            # Get the saved statement for this user
            statement = SavedStatement.query.filter_by(user_id=context.user_id).first()

            if not statement:
                return ToolResult.error_result(
                    "I don't see any uploaded statement. Please upload a bank statement first.",
                    "NO_STATEMENT"
                )

            # Parse the statement using existing analyzer
            response, analysis = analyze_statement(
                statement.raw_file,
                statement.filename,
                return_analysis=True
            )

            if not analysis:
                return ToolResult.error_result(
                    "I couldn't parse that statement. Please make sure it's a valid PDF or CSV bank statement.",
                    "PARSE_ERROR"
                )

            # Extract key data
            transactions = analysis.get("transactions", [])
            ending_balance = analysis.get("ending_balance", 0)
            total_income = analysis.get("total_income", 0)
            total_expenses = analysis.get("total_expenses", 0)
            top_categories = analysis.get("top_categories", [])
            friendly_summary = analysis.get("friendly_summary", "")

            # Enhanced analysis
            insights = []
            recurring_transactions = []
            anomalies = []

            if analysis_depth == "detailed":
                # Detect recurring transactions
                if detect_recurring and transactions:
                    recurring_transactions = self._detect_recurring_transactions(transactions)
                    if recurring_transactions:
                        recurring_total = sum(abs(r.get("amount", 0)) for r in recurring_transactions)
                        insights.append(
                            f"I found {len(recurring_transactions)} recurring transactions "
                            f"totaling ${recurring_total:,.2f}/month."
                        )

                # Detect anomalies
                if detect_anomalies and transactions:
                    anomalies = self._detect_anomalies(transactions)
                    if anomalies:
                        insights.append(
                            f"I noticed {len(anomalies)} unusual transaction(s) that might need your attention."
                        )

                # Spending insights
                if top_categories:
                    top_cat = top_categories[0] if top_categories else None
                    if top_cat:
                        insights.append(
                            f"Your top spending category is {top_cat['category']} at ${top_cat['amount']:,.2f}."
                        )

                # Balance insight
                if ending_balance and total_expenses:
                    expense_ratio = total_expenses / ending_balance if ending_balance > 0 else 0
                    if expense_ratio > 0.8:
                        insights.append(
                            "Heads up: Your expenses are quite high relative to your balance. "
                            "Consider reviewing your spending."
                        )

            # Import transactions to database if we have them
            imported_count = 0
            if transactions:
                imported_count = await self._import_transactions(
                    context.user_id,
                    transactions,
                    statement.statement_start_date,
                    statement.statement_end_date
                )

            # Build response message
            if friendly_summary:
                message = friendly_summary
            else:
                message = f"I've analyzed your statement. "
                message += f"Ending balance: ${ending_balance:,.2f}. "
                if total_expenses > 0:
                    message += f"Total spending: ${total_expenses:,.2f}. "

            # Add insights
            if insights:
                message += "\n\n" + " ".join(insights)

            # Build visual payload
            visual = self._build_visual(top_categories, total_income)

            return ToolResult.success_result(
                data={
                    "ending_balance": ending_balance,
                    "total_income": total_income,
                    "total_expenses": total_expenses,
                    "transaction_count": len(transactions),
                    "imported_count": imported_count,
                    "top_categories": top_categories,
                    "recurring_transactions": recurring_transactions[:5],
                    "anomalies": anomalies[:3],
                    "statement_period": {
                        "start": str(statement.statement_start_date) if statement.statement_start_date else None,
                        "end": str(statement.statement_end_date) if statement.statement_end_date else None,
                    }
                },
                message=message,
                visual=visual,
                suggestions=[
                    "Show my spending by category",
                    "What are my recurring expenses?",
                    "How can I reduce spending?"
                ]
            )

        except Exception as e:
            return ToolResult.error_result(
                f"Failed to analyze statement: {str(e)}",
                "ANALYSIS_ERROR"
            )

    def _detect_recurring_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """
        Detect recurring transactions (subscriptions, bills).

        Looks for:
        - Same merchant with similar amounts
        - Regular intervals (weekly, biweekly, monthly)
        """
        recurring = []

        # Group by description/merchant
        by_merchant: Dict[str, List[Dict]] = defaultdict(list)
        for tx in transactions:
            desc = (tx.get("description", "") or "").lower()[:30]
            if desc:
                by_merchant[desc].append(tx)

        # Check for patterns
        for merchant, txs in by_merchant.items():
            if len(txs) >= 2:
                # Check if amounts are similar
                amounts = [abs(tx.get("amount", 0)) for tx in txs]
                avg_amount = sum(amounts) / len(amounts)

                # If all amounts within 10% of average, likely recurring
                if all(abs(a - avg_amount) / avg_amount < 0.1 for a in amounts if avg_amount > 0):
                    # Determine frequency
                    dates = [tx.get("date") for tx in txs if tx.get("date")]
                    frequency = self._determine_frequency(dates)

                    recurring.append({
                        "merchant": merchant.title(),
                        "amount": round(avg_amount, 2),
                        "frequency": frequency,
                        "occurrences": len(txs)
                    })

        # Sort by amount descending
        return sorted(recurring, key=lambda x: -x["amount"])

    def _determine_frequency(self, dates: List[str]) -> str:
        """Determine the frequency of recurring transactions."""
        if len(dates) < 2:
            return "unknown"

        # Parse dates and calculate intervals
        parsed = []
        for d in dates:
            try:
                if isinstance(d, str):
                    parsed.append(datetime.strptime(d, "%Y-%m-%d").date())
                elif isinstance(d, date):
                    parsed.append(d)
            except (ValueError, TypeError):
                continue

        if len(parsed) < 2:
            return "unknown"

        parsed.sort()
        intervals = [(parsed[i+1] - parsed[i]).days for i in range(len(parsed)-1)]
        avg_interval = sum(intervals) / len(intervals)

        if avg_interval <= 8:
            return "weekly"
        elif avg_interval <= 16:
            return "biweekly"
        elif avg_interval <= 35:
            return "monthly"
        elif avg_interval <= 100:
            return "quarterly"
        else:
            return "yearly"

    def _detect_anomalies(self, transactions: List[Dict]) -> List[Dict]:
        """
        Detect anomalous transactions.

        Flags:
        - Unusually large amounts
        - Unexpected merchants
        - Duplicate charges
        """
        anomalies = []

        # Calculate statistics
        amounts = [abs(tx.get("amount", 0)) for tx in transactions if tx.get("amount")]
        if not amounts:
            return []

        avg_amount = sum(amounts) / len(amounts)
        # Simple std dev approximation
        variance = sum((a - avg_amount) ** 2 for a in amounts) / len(amounts)
        std_dev = variance ** 0.5

        threshold = avg_amount + (2 * std_dev)

        for tx in transactions:
            amount = abs(tx.get("amount", 0))
            desc = tx.get("description", "")

            # Flag large transactions
            if amount > threshold and amount > 100:
                anomalies.append({
                    "type": "large_transaction",
                    "description": desc,
                    "amount": round(amount, 2),
                    "reason": f"This ${amount:,.2f} charge is larger than usual."
                })

        # Check for duplicate charges (same amount, same day)
        by_date_amount: Dict[str, List[Dict]] = defaultdict(list)
        for tx in transactions:
            key = f"{tx.get('date')}_{abs(tx.get('amount', 0)):.2f}"
            by_date_amount[key].append(tx)

        for key, txs in by_date_amount.items():
            if len(txs) > 1:
                tx = txs[0]
                anomalies.append({
                    "type": "possible_duplicate",
                    "description": tx.get("description", ""),
                    "amount": abs(tx.get("amount", 0)),
                    "count": len(txs),
                    "reason": f"Found {len(txs)} similar charges on the same day."
                })

        return anomalies[:5]  # Limit to top 5

    async def _import_transactions(
        self,
        user_id: int,
        transactions: List[Dict],
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> int:
        """Import transactions to the database."""
        try:
            from db_models import db, Transaction

            imported = 0
            for tx in transactions:
                tx_date = tx.get("date")
                if isinstance(tx_date, str):
                    try:
                        tx_date = datetime.strptime(tx_date, "%Y-%m-%d").date()
                    except ValueError:
                        tx_date = date.today()
                elif not isinstance(tx_date, date):
                    tx_date = date.today()

                amount = tx.get("amount", 0)
                desc = tx.get("description", "")
                category = tx.get("category", "other")

                # Determine transaction type
                tx_type = "income" if amount > 0 else "expense"

                # Check for existing transaction (avoid duplicates)
                existing = Transaction.query.filter_by(
                    user_id=user_id,
                    amount=abs(amount),
                    transaction_date=tx_date,
                    description=desc[:200] if desc else None
                ).first()

                if not existing:
                    new_tx = Transaction(
                        user_id=user_id,
                        amount=abs(amount),
                        transaction_type=tx_type,
                        category=category.lower() if category else "other",
                        description=desc[:500] if desc else None,
                        transaction_date=tx_date,
                        source="statement"
                    )
                    db.session.add(new_tx)
                    imported += 1

            db.session.commit()
            return imported

        except Exception as e:
            print(f"Transaction import error: {e}")
            return 0

    def _build_visual(
        self,
        categories: List[Dict],
        total_income: float
    ) -> Optional[Dict[str, Any]]:
        """Build visual payload from categories."""
        if not categories:
            return None

        nodes = []

        # Add income node if available
        if total_income and total_income > 0:
            nodes.append(SankeyNode(
                id="income",
                name="Income",
                value=float(total_income)
            ))

        # Add category nodes
        for cat in categories[:6]:
            cat_name = cat.get("category", "Other")
            cat_amount = cat.get("amount", 0)
            if isinstance(cat_amount, str):
                try:
                    cat_amount = float(cat_amount.replace(",", "").replace("$", ""))
                except ValueError:
                    cat_amount = 0

            if cat_amount > 0:
                nodes.append(SankeyNode(
                    id=cat_name.lower().replace(" ", "_"),
                    name=cat_name,
                    value=round(float(cat_amount), 2)
                ))

        if nodes:
            return VisualPayload.sankey_flow(nodes)

        return None
