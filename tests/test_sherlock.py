import pytest
import requests
from requests.exceptions import Timeout
import re
import sys
import signal
import csv
import pandas as pd
from time import monotonic
from json import loads as json_loads
from argparse import ArgumentParser, RawDescriptionHelpFormatter, ArgumentTypeError
from requests.exceptions import RequestException
from sherlock_project.sherlock import sherlock, SherlockFuturesSession
from sherlock_project.result import QueryStatus
import types

def test_helper_functions():
    """
    Test helper functions in the sherlock module:
    - interpolate_string correctly handles strings, lists, dicts, and other types.
    - multiple_usernames correctly replaces the '{?}' pattern by various symbols.
    - timeout_check returns a float for valid inputs and raises an error for invalid ones.
    - check_for_parameter returns True when the username contains '{?}', otherwise False.
    """
    # Import functions and ArgumentTypeError from the sherlock module.
    from sherlock_project.sherlock import (
        interpolate_string,
        multiple_usernames,
        timeout_check,
        check_for_parameter,
    )
    from argparse import ArgumentTypeError
    # Test interpolate_string with a plain string.
    assert interpolate_string("Hello, {}", "World") == "Hello, World"
    
    # Test interpolate_string with a dictionary having nested structures.
    nested_input = {"greeting": "Hi, {}", "details": {"name": "{}"}}
    expected_output = {"greeting": "Hi, Alice", "details": {"name": "Alice"}}
    assert interpolate_string(nested_input, "Alice") == expected_output
    # Test interpolate_string with a list.
    list_input = ["{}", {"salutation": "{}"}]
    expected_list = ["Bob", {"salutation": "Bob"}]
    assert interpolate_string(list_input, "Bob") == expected_list
    # Test interpolate_string with a non-string type (should return the object unchanged).
    assert interpolate_string(123, "test") == 123
    # Test multiple_usernames replacement.
    # Given the global pattern '{?}', it should be replaced by '_', '-', and '.'.
    assert multiple_usernames("user{?}") == ["user_", "user-", "user."]
    # Test timeout_check for valid input.
    result = timeout_check("30")
    assert isinstance(result, float)
    assert result == 30.0
    # Test timeout_check for non-positive values.
    with pytest.raises(ArgumentTypeError):
        timeout_check("0")
    with pytest.raises(ArgumentTypeError):
        timeout_check("-10")
    # Test check_for_parameter to detect the pattern '{?}'.
    assert check_for_parameter("name{?}") is True
    assert check_for_parameter("username") is False
def test_get_response_timeout():
    """
    Test get_response() by simulating a Timeout exception.
    Verifies that on a timeout the function returns a None response,
    an error context of "Timeout Error", and the simulated timeout message as exception text.
    """
    from sherlock_project.sherlock import get_response
    class DummyFuture:
        def result(self):
            raise Timeout("Simulated timeout error")
    dummy_future = DummyFuture()
    response, error_context, exception_text = get_response(dummy_future, "status_code", "dummy_site")
    assert response is None
    assert error_context == "Timeout Error"
    assert "Simulated timeout error" in exception_text
def test_get_response_success():
    """
    Test get_response() by simulating a successful response.
    Verifies that when no exception is raised the function returns the dummy response,
    error_context as None, and exception_text as None.
    """
    # Import get_response from the sherlock module.
    from sherlock_project.sherlock import get_response
    # Define a dummy response object to simulate a successful HTTP request.
    class DummyResponse:
        def __init__(self):
            self.status_code = 200
            self.text = "Everything is OK"
            self.encoding = "utf-8"
            self.elapsed = 0.456
    # Define a dummy future whose result() method returns the dummy response.
    class DummyFuture:
        def result(self):
            return DummyResponse()
    dummy_future = DummyFuture()
    # Call get_response with the dummy future.
    response, error_context, exception_text = get_response(
        request_future=dummy_future, error_type="status_code", social_network="dummy_site"
    )
    # Assert that the response is the dummy response, error_context is None (or falsey)
    # and exception_text is None.
    assert isinstance(response, DummyResponse)
    # Since the code assigns error_context = None if response.status_code exists,
    # we expect error_context to be None.
    assert error_context is None
    # No exception was raised so exception_text should be None.
    assert exception_text is None
def test_sherlock_illegal_username():
    """
    Test that sherlock() correctly flags a username as illegal
    when it does not match the regexCheck in the site_data.
    """
    from sherlock_project.sherlock import sherlock
    from sherlock_project.result import QueryStatus
    # Define a dummy notify class that does nothing
    class DummyNotify:
        def start(self, username):
            pass
        def update(self, result):
            pass
        def finish(self):
            return 0
    dummy_notify = DummyNotify()
    # Create a dummy site data dict, where the regexCheck allows only letters.
    site_data = {
        "TestSite": {
            "urlMain": "https://testsite.com",
            "url": "https://testsite.com/{}",
            "regexCheck": "^[a-zA-Z]+$",  # only letters allowed; digits will not match
            "errorType": "status_code",
            "errorCode": [404],
        }
    }
    # Use a username that will not match the regex (only digits)
    username = "12345"
    results = sherlock(username, site_data, dummy_notify)
    # Check that the result for TestSite is marked as ILLEGAL.
    status = results["TestSite"]["status"]
    assert status.status == QueryStatus.ILLEGAL, "Username should be flagged as illegal by regexCheck"
    # Also, url_user, http_status, and response_text should be empty strings.
    assert results["TestSite"]["url_user"] == ""
    assert results["TestSite"]["http_status"] == ""
    assert results["TestSite"]["response_text"] == ""
def test_sherlock_message_branch(monkeypatch):
    """
    Test the 'message' detection branch in sherlock().
    This test simulates an HTTP response (via monkeypatching) where the response text
    does not contain the error message specified in the site_data.
    As a result, the function should mark the username as claimed.
    """
    from sherlock_project.sherlock import sherlock, SherlockFuturesSession
    from sherlock_project.result import QueryStatus
    # Define dummy response and future classes to simulate HTTP calls.
    class DummyResponse:
        def __init__(self, text, status_code=200, elapsed=0.111, encoding='utf-8'):
            self.status_code = status_code
            self.text = text
            self.elapsed = elapsed
            self.encoding = encoding
    class DummyFuture:
        def result(self):
            return DummyResponse(text="Profile exists for user")
    
    # Monkeypatch the request method of SherlockFuturesSession to always return our DummyFuture.
    monkeypatch.setattr(SherlockFuturesSession, "request",
                        lambda self, method, url, hooks=None, *args, **kwargs: DummyFuture())
    # Create a dummy notify object
    class DummyNotify:
        def start(self, username):
            pass
        def update(self, result):
            self.result = result
        def finish(self):
            return 0
    dummy_notify = DummyNotify()
    # Construct site_data for a site that uses the 'message' error detection branch.
    # The errorMsg 'Not Found' is not present in our dummy response text,
    # so the username should be flagged as claimed.
    site_data = {
        "TestMessage": {
            "urlMain": "https://testmessage.com",
            "url": "https://testmessage.com/{}",
            "errorType": "message",
            "errorMsg": "Not Found",
        }
    }
    username = "testuser"
    results = sherlock(username, site_data, dummy_notify)
    result = results["TestMessage"]["status"]
    # Since "Not Found" does not appear in the dummy text,
    # the error flag stays true and the query status becomes CLAIMED.
    assert result.status == QueryStatus.CLAIMED
    assert result.query_time == 0.111
def test_sherlock_response_url_branch(monkeypatch):
    """
    Test the 'response_url' detection branch in sherlock().
    This test simulates an HTTP response (via monkeypatching)
    where the response has a status code outside of the 200-299 range.
    As a result, the function should mark the username as available.
    """
    from sherlock_project.sherlock import sherlock, SherlockFuturesSession
    from sherlock_project.result import QueryStatus
    # Define a dummy response to simulate a non-successful response.
    class DummyResponse:
        def __init__(self):
            self.status_code = 404  # Not in 200-299 range.
            self.text = "Not Found"
            self.elapsed = 0.200
            self.encoding = 'utf-8'
    # Define a dummy future that returns the DummyResponse.
    class DummyFuture:
        def result(self):
            return DummyResponse()
    # Monkeypatch the 'request' method of SherlockFuturesSession to always return our DummyFuture.
    monkeypatch.setattr(
        SherlockFuturesSession, "request",
        lambda self, method, url, hooks=None, *args, **kwargs: DummyFuture()
    )
    # Create a dummy notify class that simply records the last result.
    class DummyNotify:
        def start(self, username):
            pass
        def update(self, result):
            self.result = result
        def finish(self):
            return 0
    dummy_notify = DummyNotify()
    # Construct site_data for a site that uses the 'response_url' error detection branch.
    site_data = {
        "TestResponseURL": {
            "urlMain": "https://testresponseurl.com",
            "url": "https://testresponseurl.com/{}",
            "errorType": "response_url",
        }
    }
    username = "testuser"
    results = sherlock(username, site_data, dummy_notify)
    result_obj = results["TestResponseURL"]["status"]
    # For errorType "response_url", a response status code outside 200-299 should mark the username as AVAILABLE.
    assert result_obj.status == QueryStatus.AVAILABLE
    assert result_obj.query_time == 0.200
def test_sherlock_unknown_error_type(monkeypatch):
    """
    Test that sherlock() raises a ValueError for an unsupported errorType.
    This covers the branch in the function where an unknown error detection method is provided.
    """
    # Define dummy response and future classes.
    class DummyResponse:
        def __init__(self):
            self.status_code = 200
            self.text = "Dummy response"
            self.elapsed = 0.123
            self.encoding = "utf-8"
    class DummyFuture:
        def result(self):
            return DummyResponse()
    # Monkeypatch the request method of SherlockFuturesSession to always return our DummyFuture.
    monkeypatch.setattr(
        SherlockFuturesSession,
        "request",
        lambda self, method, url, hooks=None, *args, **kwargs: DummyFuture(),
    )
    # Create a dummy notify object that does nothing.
    class DummyNotify:
        def start(self, username):
            pass
        def update(self, result):
            self.result = result
        def finish(self):
            return 0
    dummy_notify = DummyNotify()
    # Create a site_data entry with an unsupported errorType.
    site_data = {
        "TestUnknown": {
            "urlMain": "https://unknown.com",
            "url": "https://unknown.com/{}",
            "errorType": "unsupported_method",  # unsupported error detection method
        }
    }
    # Ensure that calling sherlock() with the unsupported errorType raises a ValueError.
    with pytest.raises(ValueError) as exc_info:
        sherlock("testuser", site_data, dummy_notify)
    assert "Unknown Error Type" in str(exc_info.value)
def test_sherlock_status_code_branch(monkeypatch):
    """
    Test the 'status_code' detection branch in sherlock().
    This test simulates two HTTP responses:
    - One with status code 200 (which should result in a CLAIMED status).
    - One with status code 404 (which is provided in errorCode and should result in an AVAILABLE status).
    """
    # Define a dummy response class to simulate HTTP responses with different status codes.
    class DummyResponse:
        def __init__(self, status_code, text="Dummy response", elapsed=0.100, encoding="utf-8"):
            self.status_code = status_code
            self.text = text
            self.elapsed = elapsed
            self.encoding = encoding
    # Define a dummy future that returns the DummyResponse.
    class DummyFuture:
        def __init__(self, response):
            self._response = response
        def result(self):
            return self._response
    # Create a dummy notify class to capture the result.
    class DummyNotify:
        def start(self, username):
            pass
        def update(self, result):
            self.result = result
        def finish(self):
            return 0
    dummy_notify = DummyNotify()
    # Site data to use for testing the "status_code" branch.
    site_data = {
        "TestStatus": {
            "urlMain": "https://teststatus.com",
            "url": "https://teststatus.com/{}",
            "errorType": "status_code",
            "errorCode": 404,  # Either an int or list; our test will use 404
        }
    }
    username = "validuser"
    # First test: simulate a response with status code 200.
    def dummy_request_200(self, method, url, hooks=None, *args, **kwargs):
        return DummyFuture(DummyResponse(200, elapsed=0.150))
    monkeypatch.setattr(SherlockFuturesSession, "request", dummy_request_200)
    results_200 = sherlock(username, site_data, dummy_notify)
    result_200 = results_200["TestStatus"]["status"]
    # For status_code 200 (which is not in the errorCode list and is within normal range),
    # the username should be considered CLAIMED.
    assert result_200.status == QueryStatus.CLAIMED
    assert result_200.query_time == 0.150
    # Second test: simulate a response with status code 404.
    def dummy_request_404(self, method, url, hooks=None, *args, **kwargs):
        return DummyFuture(DummyResponse(404, elapsed=0.250))
    monkeypatch.setattr(SherlockFuturesSession, "request", dummy_request_404)
    results_404 = sherlock(username, site_data, dummy_notify)
    result_404 = results_404["TestStatus"]["status"]
    # Since 404 is provided in errorCode, the username should be marked as AVAILABLE.
    assert result_404.status == QueryStatus.AVAILABLE
    assert result_404.query_time == 0.250
def test_sherlock_tor_import_error(monkeypatch, capsys):
    """
    Test that sherlock() exits when tor is enabled but the torrequest module is missing.
    This simulates an ImportError when trying to import TorRequest, verifying that the
    tor branch prints the warning messages and calls sys.exit.
    """
    # Monkeypatch __import__ to force ImportError when "torrequest" is requested.
    original_import = __import__
    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "torrequest":
            raise ImportError("No module named 'torrequest'")
        return original_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr("builtins.__import__", fake_import)
    # Create a dummy notify class whose finish() returns an exit code.
    class DummyNotify:
        def start(self, username):
            pass
        def update(self, result):
            pass
        def finish(self):
            return 1
    dummy_notify = DummyNotify()
    # Prepare a dummy site_data (although it won't be used because we're exiting early).
    site_data = {
        "FakeSite": {
            "urlMain": "https://fakesite.com",
            "url": "https://fakesite.com/{}",
            "errorType": "status_code",
            "errorCode": 404,
        }
    }
    # Import sherlock() from the source.
    from sherlock_project.sherlock import sherlock
    # When tor is True, the ImportError from torrequest should force a sys.exit.
    with pytest.raises(SystemExit) as exit_info:
        sherlock("dummyuser", site_data, dummy_notify, tor=True)
    output = capsys.readouterr().out
    # Check that the warning messages were printed.
    assert "Important!" in output
    # Check that the exit code matches what DummyNotify.finish() returns.
    assert exit_info.value.code == 1
def test_sherlock_unique_tor(monkeypatch):
    """
    Test that when using the --unique-tor option, Sherlock calls
    the TorRequest.reset_identity() method once per site after submitting the request.
    This test creates a dummy torrequest module with a DummyTorRequest that counts reset_identity() calls.
    """
    # Import the original source code
    from sherlock_project.sherlock import sherlock, SherlockFuturesSession
    from sherlock_project.result import QueryStatus
    # Define a dummy TorRequest that simulates tor functionality.
    class DummyTorRequest:
        reset_counter = 0
        def __init__(self):
            self.session = requests.Session()
        def reset_identity(self):
            DummyTorRequest.reset_counter += 1
    # Create a dummy torrequest module with our DummyTorRequest.
    dummy_torrequest = types.ModuleType("torrequest")
    dummy_torrequest.TorRequest = DummyTorRequest
    # Monkeypatch sys.modules to include our dummy torrequest module.
    monkeypatch.setitem(sys.modules, "torrequest", dummy_torrequest)
    # Reset the counter before test.
    DummyTorRequest.reset_counter = 0
    # Define dummy response classes to simulate a successful HTTP response.
    class DummyResponse:
        def __init__(self, status_code=200, text="OK", elapsed=0.100, encoding="utf-8"):
            self.status_code = status_code
            self.text = text
            self.elapsed = elapsed
            self.encoding = encoding
    class DummyFuture:
        def result(self):
            return DummyResponse()
    # Monkeypatch the request method of SherlockFuturesSession to always return DummyFuture.
    monkeypatch.setattr(SherlockFuturesSession, "request",
                        lambda self, method, url, hooks=None, *args, **kwargs: DummyFuture())
    # Define a dummy notify class to pass into sherlock().
    class DummyNotify:
        def start(self, username):
            pass
        def update(self, result):
            self.result = result
        def finish(self):
            return 0
    dummy_notify = DummyNotify()
    # Construct site_data with one site using the 'status_code' branch.
    site_data = {
        "TorTestSite": {
            "urlMain": "https://tortest.com",
            "url": "https://tortest.com/{}",
            "errorType": "status_code",
            "errorCode": [404],
        }
    }
    username = "uniqueuser"
    # Call sherlock with tor=True and unique_tor=True. This will force the branch and call reset_identity() once per site.
    results = sherlock(username, site_data, dummy_notify, tor=True, unique_tor=True)
    # Since site_data contains one site, we expect reset_identity() to have been called once.
    assert DummyTorRequest.reset_counter == 1, "Expected reset_identity() to be called once for one site."
    # Additionally, check that the response for the site is as expected (claimed since status=200 and errorCode is 404).
    result_obj = results["TorTestSite"]["status"]
    assert result_obj.status == QueryStatus.CLAIMED
    assert result_obj.query_time == 0.100