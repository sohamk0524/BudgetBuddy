"""
Gamification service — streak calculation, weekly challenge generation, and progress tracking.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


def calculate_streak(user_id: str) -> Tuple[int, int]:
    """Calculate the user's current and longest savings streak (consecutive on-budget weeks).

    Returns (current_streak, longest_streak).
    """
    from db_models import get_manual_transactions, get_profile

    profile = get_profile(user_id)
    weekly_limit = float(profile.get('weekly_spending_limit', 0)) if profile else 0
    if weekly_limit <= 0:
        return 0, 0

    transactions = get_manual_transactions(user_id)
    if not transactions:
        return 0, 0

    # Group transaction amounts by ISO week (Mon-Sun)
    weekly_totals: Dict[str, float] = {}
    for txn in transactions:
        created = txn.get('created_at')
        if not created:
            continue
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                continue
        if hasattr(created, 'tzinfo') and created.tzinfo is not None:
            created = created.replace(tzinfo=None)
        iso_year, iso_week, _ = created.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        amount = abs(float(txn.get('amount', 0)))
        weekly_totals[week_key] = weekly_totals.get(week_key, 0) + amount

    if not weekly_totals:
        return 0, 0

    # Build sorted list of completed past weeks
    now = datetime.utcnow()
    current_iso = now.isocalendar()
    current_week_key = f"{current_iso[0]}-W{current_iso[1]:02d}"

    sorted_weeks = sorted(weekly_totals.keys(), reverse=True)

    # Count consecutive on-budget weeks backwards (skip current incomplete week)
    current_streak = 0
    longest_streak = 0
    running = 0

    # Get all weeks from earliest transaction to last completed week
    all_week_keys = sorted(weekly_totals.keys())
    if not all_week_keys:
        return 0, 0

    for week_key in reversed(all_week_keys):
        if week_key == current_week_key:
            continue  # Skip current incomplete week
        spent = weekly_totals.get(week_key, 0)
        if spent <= weekly_limit:
            running += 1
            longest_streak = max(longest_streak, running)
        else:
            running = 0

    # Current streak: count backwards from most recent completed week
    current_streak = 0
    for week_key in reversed(all_week_keys):
        if week_key == current_week_key:
            continue
        spent = weekly_totals.get(week_key, 0)
        if spent <= weekly_limit:
            current_streak += 1
        else:
            break

    return current_streak, longest_streak


def generate_weekly_challenge(user_id: str, exclude_category: str = None) -> Optional[Dict]:
    """Generate a weekly challenge based on the user's top spending category from last week.

    Returns a challenge dict or None if insufficient data.
    If exclude_category is given, skip that category (used when declining a challenge).
    """
    from db_models import get_manual_transactions, get_category_prefs

    transactions = get_manual_transactions(user_id)
    if not transactions:
        return None

    now = datetime.utcnow()
    current_iso = now.isocalendar()

    # Find last week's Monday-Sunday
    days_since_monday = now.weekday()  # 0=Mon
    this_monday = now - timedelta(days=days_since_monday)
    last_monday = this_monday - timedelta(days=7)
    last_sunday = this_monday - timedelta(days=1)

    last_week_start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    last_week_end = last_sunday.replace(hour=23, minute=59, second=59)

    # Sum spending by category for last week
    category_totals: Dict[str, float] = {}
    for txn in transactions:
        created = txn.get('created_at')
        if not created:
            continue
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                continue
        # Strip timezone info for comparison with naive datetimes
        if hasattr(created, 'tzinfo') and created.tzinfo is not None:
            created = created.replace(tzinfo=None)
        if last_week_start <= created <= last_week_end:
            cat = (txn.get('sub_category') or 'other').lower()
            amount = abs(float(txn.get('amount', 0)))
            category_totals[cat] = category_totals.get(cat, 0) + amount

    # Fall back to last 30 days if last week had no data
    if not category_totals:
        thirty_days_ago = now - timedelta(days=30)
        for txn in transactions:
            created = txn.get('created_at')
            if not created:
                continue
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except ValueError:
                    continue
            if hasattr(created, 'tzinfo') and created.tzinfo is not None:
                created = created.replace(tzinfo=None)
            if created >= thirty_days_ago:
                cat = (txn.get('sub_category') or 'other').lower()
                amount = abs(float(txn.get('amount', 0)))
                category_totals[cat] = category_totals.get(cat, 0) + amount

    if not category_totals:
        return None

    # Remove excluded category if declining
    if exclude_category:
        category_totals.pop(exclude_category.lower(), None)
    if not category_totals:
        return None

    # Find top spending category
    top_category = max(category_totals, key=category_totals.get)
    last_week_amount = category_totals[top_category]
    target_amount = round(last_week_amount * 0.85, 2)  # 15% reduction goal

    # Look up icon from category prefs
    icon = "dollarsign.circle"
    cat_prefs = get_category_prefs(user_id)
    for pref in cat_prefs:
        if (pref.get('category_name') or '').lower() == top_category:
            icon = pref.get('icon', icon)
            break

    # Week boundaries for current week
    this_monday_str = this_monday.strftime('%Y-%m-%d')
    this_sunday = this_monday + timedelta(days=6)
    this_sunday_str = this_sunday.strftime('%Y-%m-%d')

    display_name = top_category.replace('_', ' ').title()

    return {
        'category': top_category,
        'targetAmount': target_amount,
        'description': f"Spend under ${int(target_amount)} on {display_name} this week",
        'weekStart': this_monday_str,
        'weekEnd': this_sunday_str,
        'icon': icon,
        'accepted': False,
        'currentSpent': 0,  # Will be filled by get_challenge_progress
    }


def get_challenge_progress(user_id: str, category: str) -> float:
    """Sum the current week's spending in the given category."""
    from db_models import get_manual_transactions

    transactions = get_manual_transactions(user_id)
    now = datetime.utcnow()
    days_since_monday = now.weekday()
    this_monday = (now - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    total = 0.0
    for txn in transactions:
        created = txn.get('created_at')
        if not created:
            continue
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                continue
        if hasattr(created, 'tzinfo') and created.tzinfo is not None:
            created = created.replace(tzinfo=None)
        if created >= this_monday:
            cat = (txn.get('sub_category') or 'other').lower()
            if cat == category.lower():
                total += abs(float(txn.get('amount', 0)))

    return round(total, 2)


def archive_challenge(gam_entity, challenge: Dict) -> List[Dict]:
    """Archive a challenge into the history list. Returns the updated history.

    Each history entry stores: category, targetAmount, currentSpent, weekStart, weekEnd,
    accepted (bool), completed (bool — spent <= target), dismissed (bool).
    """
    history_json = gam_entity.get('challenge_history_json', '[]') if gam_entity else '[]'
    try:
        history = json.loads(history_json)
    except (json.JSONDecodeError, TypeError):
        history = []

    entry = {
        'category': challenge.get('category', ''),
        'targetAmount': challenge.get('targetAmount', 0),
        'currentSpent': challenge.get('currentSpent', 0),
        'weekStart': challenge.get('weekStart', ''),
        'weekEnd': challenge.get('weekEnd', ''),
        'accepted': challenge.get('accepted', False),
        'completed': challenge.get('currentSpent', 0) <= challenge.get('targetAmount', 0),
        'dismissed': challenge.get('dismissed', False),
        'description': challenge.get('description', ''),
        'icon': challenge.get('icon', 'dollarsign.circle'),
    }
    history.append(entry)

    # Keep last 52 weeks max
    if len(history) > 52:
        history = history[-52:]

    return history
