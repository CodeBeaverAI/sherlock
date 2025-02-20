import pytest
from sherlock_project.result import (
    QueryResult,
    QueryStatus,
)


def test_queryresult_with_context():
    """
    Test the QueryResult __str__ method when additional context is provided.
    The test creates a QueryResult with a specific context and verifies
    that the returned string includes the context in the expected format.
    """
    username = "testuser"
    site_name = "example_site"
    site_url_user = "http://example.com/testuser"
    status = QueryStatus.CLAIMED
    query_time = 0.456
    context = "Timeout occurred"
    result_obj = QueryResult(
        username, site_name, site_url_user, status, query_time, context
    )
    expected_str = "Claimed (Timeout occurred)"
    assert str(result_obj) == expected_str


def test_queryresult_without_context():
    """
    Test the QueryResult __str__ method when no additional context is provided.
    This verifies that the returned string is just the status string without
    any appended context information.
    """
    username = "anotheruser"
    site_name = "another_site"
    site_url_user = "http://anothersite.com/anotheruser"
    status = QueryStatus.AVAILABLE
    result_obj = QueryResult(username, site_name, site_url_user, status)
    expected_str = "Available"
    assert str(result_obj) == expected_str


def test_queryresult_with_empty_context():
    """
    Test the QueryResult __str__ method when an empty string is provided as context.
    This verifies that even an empty context string is appended in parentheses.
    """
    username = "emptycontextuser"
    site_name = "empty_site"
    site_url_user = "http://emptysite.com/emptycontextuser"
    status = QueryStatus.CLAIMED
    context = ""
    result_obj = QueryResult(
        username, site_name, site_url_user, status, context=context
    )
    expected_str = "Claimed ()"
    assert str(result_obj) == expected_str


def test_querystatus_str():
    """
    Test the __str__ method of QueryStatus to ensure it returns the correct
    string representation for each enumeration member.
    """
    statuses = {
        QueryStatus.CLAIMED: "Claimed",
        QueryStatus.AVAILABLE: "Available",
        QueryStatus.UNKNOWN: "Unknown",
        QueryStatus.ILLEGAL: "Illegal",
        QueryStatus.WAF: "WAF",
    }
    for status, expected_str in statuses.items():
        assert str(status) == expected_str
