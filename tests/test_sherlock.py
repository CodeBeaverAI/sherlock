import csv
import os
import pandas as pd
import pytest
import re
import requests
import signal
import sys
from argparse import (
    ArgumentTypeError,
)
from sherlock_project.result import (
    QueryResult,
    QueryStatus,
)
from sherlock_project.sherlock import (
    SherlockFuturesSession,
    check_for_parameter,
    get_response,
    interpolate_string,
    multiple_usernames,
    sherlock,
    timeout_check,
)
from time import (
    monotonic,
)

try:
    from sherlock_project.sherlock import timeout_check
except ImportError:
    pytest.skip(
        "Unable to import timeout_check from sherlock_project.sherlock",
        allow_module_level=True,
    )


def test_timeout_check_validation():
    """
    Test the timeout_check function with valid and invalid inputs.

    This test verifies that:
    - A valid timeout string is converted correctly to a float.
    - A timeout of 0 or negative value raises an ArgumentTypeError.
    """
    valid_timeout = "30"
    assert timeout_check(valid_timeout) == 30.0
    with pytest.raises(ArgumentTypeError):
        timeout_check("0")
    with pytest.raises(ArgumentTypeError):
        timeout_check("-10")


def test_interpolate_string_correct_substitution():
    """
    Test the interpolate_string function for various data types.

    This test verifies that:
    - When given a string with '{}' placeholder, it correctly replaces it.
    - When given a dictionary containing strings with '{}' placeholders (including nested dictionaries),
      it correctly performs the substitution.
    - When given a list of strings with '{}' placeholders, it correctly performs the substitution.
    - When given a value that is not a string, list, or dict, the value is returned unchanged.
    """
    input_str = "User: {}"
    expected_str = "User: testuser"
    assert interpolate_string(input_str, "testuser") == expected_str
    input_dict = {"greeting": "Hi, {}!", "nested": {"farewell": "Bye, {}!"}}
    expected_dict = {
        "greeting": "Hi, testuser!",
        "nested": {"farewell": "Bye, testuser!"},
    }
    assert interpolate_string(input_dict, "testuser") == expected_dict
    input_list = ["Welcome, {}!", "{} just logged in."]
    expected_list = ["Welcome, testuser!", "testuser just logged in."]
    assert interpolate_string(input_list, "testuser") == expected_list
    input_int = 42
    assert interpolate_string(input_int, "testuser") == 42
    input_none = None
    assert interpolate_string(input_none, "testuser") is None


def test_get_response_connection_error():
    """
    Test the get_response function to handle a ConnectionError.
    This test creates a fake Future object that raises a ConnectionError when its result() method is called,
    and then asserts that get_response returns None for the response, sets the error_context to "Error Connecting",
    and includes the exception message in the exception_text.
    """

    class FakeFuture:

        def result(self):
            raise requests.exceptions.ConnectionError("Test connection error")

    fake_future = FakeFuture()
    response, error_context, exception_text = get_response(
        fake_future, error_type="dummy", social_network="dummy"
    )
    assert response is None
    assert error_context == "Error Connecting"
    assert "Test connection error" in exception_text


class FakeResponse:
    """Fake response object for testing a successful response scenario."""

    def __init__(self, status_code=200, text="", encoding="utf-8", elapsed=0.1):
        self.status_code = status_code
        self.text = text
        self.encoding = encoding
        self.elapsed = elapsed


class FakeFutureSuccess:
    """Fake future that returns a successful FakeResponse."""

    def result(self):
        return FakeResponse()


def test_get_response_successful():
    """
    Test the get_response function for a successful response scenario.

    This test creates a FakeFutureSuccess object that returns a FakeResponse
    with a valid HTTP status code. It asserts that get_response returns the fake
    response with error_context set to None and no exception text.
    """
    fake_future = FakeFutureSuccess()
    response, error_context, exception_text = get_response(
        request_future=fake_future, error_type="dummy", social_network="dummy"
    )
    assert response is not None
    assert response.status_code == 200
    assert isinstance(response.elapsed, float)
    assert error_context is None
    assert exception_text is None


def test_multiple_usernames_replacement():
    """
    Test that the multiple_usernames function correctly replaces the "{?}" placeholder
    with all supported symbols ("_", "-", and ".").
    """
    input_username = "test{?}"
    expected = ["test_", "test-", "test."]
    result = multiple_usernames(input_username)
    assert result == expected


def test_check_for_parameter():
    """
    Test the check_for_parameter function to ensure that it correctly identifies
    whether a username contains the placeholder "{?}".

    If "{?}" is present in the username, the function should return True,
    otherwise False.
    """
    username_with_placeholder = "test{?}_user"
    assert check_for_parameter(username_with_placeholder) is True
    username_without_placeholder = "test_user"
    assert check_for_parameter(username_without_placeholder) is False


def test_get_response_timeout_error():
    """
    Test the get_response function to handle a Timeout error.
    This test creates a FakeFutureTimeout object that raises a Timeout exception
    when its result() method is called, and then asserts that get_response returns
    None for the response, sets the error_context to "Timeout Error", and includes
    the exception message in the exception_text.
    """

    class FakeFutureTimeout:

        def result(self):
            raise requests.exceptions.Timeout("Test timeout exceeded")

    fake_future = FakeFutureTimeout()
    response, error_context, exception_text = get_response(
        request_future=fake_future, error_type="dummy", social_network="dummy"
    )
    assert response is None
    assert error_context == "Timeout Error"
    assert "Test timeout exceeded" in exception_text


def test_get_response_http_error():
    """
    Test get_response function to handle an HTTPError.

    This test creates a fake Future object that raises an HTTPError when its result() method is called.
    It asserts that get_response returns None for the response, sets the error_context to "HTTP Error",
    and that the exception_text contains the raised error message.
    """

    class FakeFutureHTTPError:

        def result(self):
            raise requests.exceptions.HTTPError("Test HTTP error occurred")

    fake_future = FakeFutureHTTPError()
    response, error_context, exception_text = get_response(
        request_future=fake_future, error_type="dummy", social_network="dummy"
    )
    assert response is None
    assert error_context == "HTTP Error"
    assert "Test HTTP error occurred" in exception_text


class DummyQueryNotify:

    def __init__(self):
        self.updates = []

    def start(self, username):
        pass

    def update(self, result):
        self.updates.append(result)

    def finish(self):
        return 0


def test_sherlock_illegal_username():
    """
    Test that the sherlock function correctly marks a username as illegal when
    the provided username does not match the site's regexCheck.
    """
    dummy_site_data = {
        "dummy": {
            "url": "http://example.com/{}",
            "urlMain": "http://example.com",
            "regexCheck": "^[a-z]+$",
            "errorType": "status_code",
            "errorMsg": "Not Found",
            "errorCode": [404],
        }
    }
    illegal_username = "TestUser"
    dummy_notify = DummyQueryNotify()
    results = sherlock(
        username=illegal_username,
        site_data=dummy_site_data,
        query_notify=dummy_notify,
        tor=False,
        unique_tor=False,
        dump_response=False,
        proxy=None,
        timeout=60,
    )
    site_result = results["dummy"]
    assert site_result["status"].status == QueryStatus.ILLEGAL
    assert site_result["url_user"] == ""
    assert site_result["http_status"] == ""


class FakeFutureClaimed:

    def result(self):
        return FakeResponse(status_code=200, text="User profile exists", elapsed=0.2)


class FakeFutureAvailable:

    def result(self):
        return FakeResponse(
            status_code=200,
            text="Error: Not Found - Profile does not exist",
            elapsed=0.3,
        )


def fake_get(self, url, headers=None, allow_redirects=True, timeout=60, json=None):
    """
    A fake GET method to replace SherlockFuturesSession.get.
    It inspects a custom header "X-Fake-Response" to decide which fake future
    to return.
    """
    if headers is None:
        headers = {}
    fake_response_type = headers.get("X-Fake-Response")
    if fake_response_type == "claimed":
        return FakeFutureClaimed()
    elif fake_response_type == "available":
        return FakeFutureAvailable()
    else:
        raise ValueError("Unknown fake response type in headers.")


def test_sherlock_message_detection(monkeypatch):
    """
    Test that the sherlock function correctly processes a site with errorType 'message'
    by using a monkey-patched GET method. Two scenarios are tested:
      - For the dummy site where the fake response text does NOT include the error message,
        the account is assumed to exist (CLAIMED).
      - For the dummy site where the fake response text DOES include the error message,
        the account is considered available (AVAILABLE).
    """
    dummy_site_data = {
        "dummy_claimed": {
            "url": "http://example.com/{}",
            "urlMain": "http://example.com",
            "regexCheck": "^[a-z]+$",
            "errorType": "message",
            "errorMsg": "Not Found",
            "errorCode": [404],
            "headers": {"X-Fake-Response": "claimed"},
        },
        "dummy_available": {
            "url": "http://example.com/{}",
            "urlMain": "http://example.com",
            "regexCheck": "^[a-z]+$",
            "errorType": "message",
            "errorMsg": "Not Found",
            "errorCode": [404],
            "headers": {"X-Fake-Response": "available"},
        },
    }
    username = "testuser"
    dummy_notify = DummyQueryNotify()
    monkeypatch.setattr(SherlockFuturesSession, "get", fake_get)
    results = sherlock(
        username=username,
        site_data=dummy_site_data,
        query_notify=dummy_notify,
        tor=False,
        unique_tor=False,
        dump_response=False,
        proxy=None,
        timeout=60,
    )
    expected_url = "http://example.com/testuser"
    result_claimed = results["dummy_claimed"]["status"]
    assert result_claimed.status == QueryStatus.CLAIMED
    assert results["dummy_claimed"]["url_user"] == expected_url
    result_available = results["dummy_available"]["status"]
    assert result_available.status == QueryStatus.AVAILABLE
    assert results["dummy_available"]["url_user"] == expected_url
