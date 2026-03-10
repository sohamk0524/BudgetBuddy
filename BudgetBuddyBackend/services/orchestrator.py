"""
Orchestrator service — now a thin wrapper.

The chat agent has been removed (ChatView is not in the iOS app navigation).
Only _build_user_context remains for any callers that still reference it;
the recommendations generator now has its own lean version.
"""
