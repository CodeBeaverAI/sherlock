import pytest
import re
import sherlock_project.notify as notify_mod
import webbrowser
from sherlock_project.notify import (
    QueryNotify,
    QueryNotifyPrint,
    globvar,
)
from sherlock_project.result import (
    QueryStatus,
)


class DummyQueryResult:
    """Dummy query result class used for testing.
    This object simulates the QueryResult() expected by the notify module."""

    def __init__(
        self,
        status,
        site_name="dummy_site",
        query_time=None,
        site_url_user="http://dummy.com",
        context="dummy context",
    ):
        self.status = status
        self.site_name = site_name
        self.query_time = query_time
        self.site_url_user = site_url_user
        self.context = context

    def __str__(self):
        return f"DummyQueryResult({self.status}, {self.site_name})"


def test_update_with_invalid_status_raises_value_error():
    """
    Test that the update method in QueryNotifyPrint raises ValueError when the DummyQueryResult
    object contains an invalid query status.
    """
    invalid_status = "NON_EXISTENT_STATUS"
    dummy_result = DummyQueryResult(status=invalid_status)
    notifier = QueryNotifyPrint(verbose=True, print_all=True, browse=False)
    with pytest.raises(ValueError) as exc_info:
        notifier.update(dummy_result)
    assert "Unknown Query Status" in str(exc_info.value)


def strip_ansi(text):
    """
    Strip ANSI escape sequences from the text.
    """
    ansi_escape = re.compile("\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def test_update_claimed_calls_webbrowser_and_prints(monkeypatch, capsys):
    """
    Test that the update method for a CLAIMED query result with browse enabled:
    - Calls webbrowser.open with the correct URL and parameter.
    - Prints expected output, ignoring ANSI escape sequences.
    """
    webbrowser_calls = []

    def fake_open(url, new):
        webbrowser_calls.append((url, new))

    monkeypatch.setattr(webbrowser, "open", fake_open)
    dummy_result = DummyQueryResult(
        status=QueryStatus.CLAIMED,
        site_name="dummy_site",
        query_time=0.005,
        site_url_user="http://example.com",
    )
    notifier = QueryNotifyPrint(verbose=True, print_all=True, browse=True)
    notifier.update(dummy_result)
    captured = capsys.readouterr().out
    plain_output = strip_ansi(captured)
    assert "[+" in plain_output, "Expected marker '[+' in output"
    assert "dummy_site:" in plain_output, "Expected site name in output"
    assert "5ms" in plain_output, "Expected formatted query time in output"
    assert len(webbrowser_calls) == 1, "Expected one call to webbrowser.open"
    assert webbrowser_calls[0] == (
        "http://example.com",
        2,
    ), "webbrowser.open called with wrong arguments"


def test_finish_prints_correct_output(capsys):
    """
    Test that the finish method prints the correct output message with "Search completed"
    and indicates 0 results after resetting the global counter.
    This test strips ANSI escape sequences from the output before checking.
    """
    notify_mod.globvar = 0
    notifier = QueryNotifyPrint(verbose=False, print_all=True, browse=False)
    notifier.finish()
    captured = capsys.readouterr().out
    captured_plain = strip_ansi(captured)
    assert (
        "Search completed" in captured_plain
    ), "Finish message should contain 'Search completed'"
    assert "0 results" in captured_plain, "Finish message should indicate 0 results"


def test_update_unknown_prints_output(capsys):
    """
    Test that the update method for an UNKNOWN query result prints the expected output.
    It verifies that the output contains the site name and the context message.
    """
    dummy_result = DummyQueryResult(
        status=QueryStatus.UNKNOWN,
        site_name="dummy_unknown",
        query_time=0.01,
        site_url_user="http://dummy.com",
        context="Test context unknown",
    )
    notifier = QueryNotifyPrint(verbose=False, print_all=True, browse=False)
    notifier.update(dummy_result)
    captured = capsys.readouterr().out
    plain_output = re.sub("\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])", "", captured)
    assert "dummy_unknown:" in plain_output, "Site name not printed as expected."
    assert "Test context unknown" in plain_output, "Context not printed as expected."


def test_update_available_prints_output(capsys):
    """
    Test that the update method for an AVAILABLE query result prints the expected output.
    It verifies that the output contains the site name, the 'Not Found!' message and the
    correctly formatted response time when verbose output is enabled.
    """
    dummy_result = DummyQueryResult(
        status=QueryStatus.AVAILABLE,
        site_name="dummy_available",
        query_time=0.002,
        site_url_user="http://dummyavailable.com",
        context="irrelevant",
    )
    notifier = QueryNotifyPrint(verbose=True, print_all=True, browse=False)
    notifier.update(dummy_result)
    captured = capsys.readouterr().out
    plain_output = re.sub("\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])", "", captured)
    assert (
        "dummy_available:" in plain_output
    ), "Site name should be printed for AVAILABLE result"
    assert (
        "Not Found!" in plain_output
    ), "Expected output to indicate 'Not Found!' for AVAILABLE result"
    assert "2ms" in plain_output, "Expected response time to be printed correctly"


def test_update_illegal_prints_output(capsys):
    """
    Test that the update method for an ILLEGAL query result prints the expected output message.
    It verifies that the printed output contains the site name and the illegal username format message.
    """
    dummy_result = DummyQueryResult(
        status=QueryStatus.ILLEGAL,
        site_name="dummy_illegal",
        query_time=0.0,
        site_url_user="http://dummyillegal.com",
    )
    notifier = QueryNotifyPrint(verbose=False, print_all=True, browse=False)
    notifier.update(dummy_result)
    captured = capsys.readouterr().out
    plain_output = re.sub("\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])", "", captured)
    assert (
        "dummy_illegal:" in plain_output
    ), "Site name not printed as expected for ILLEGAL status."
    assert (
        "Illegal Username Format For This Site!" in plain_output
    ), "Expected illegal username format message in output."


def test_update_waf_prints_output(capsys):
    """
    Test that the update method for a WAF query result prints the expected output.
    It verifies that when the dummy query result's status is set to WAF,
    the output indicates that the request was blocked by bot detection and suggests that a proxy may help.
    """
    dummy_result = DummyQueryResult(
        status=QueryStatus.WAF,
        site_name="dummy_waf",
        query_time=0.003,
        site_url_user="http://dummywaf.com",
        context="irrelevant",
    )
    notifier = QueryNotifyPrint(verbose=False, print_all=True, browse=False)
    notifier.update(dummy_result)
    captured = capsys.readouterr().out
    plain_output = re.sub("\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])", "", captured)
    assert (
        "dummy_waf:" in plain_output
    ), "Site name not printed as expected for WAF status."
    assert (
        "Blocked by bot detection" in plain_output
    ), "Expected WAF block message in output."
    assert (
        "proxy may help" in plain_output
    ), "Expected suggestion that proxy may help in output."


def test_start_prints_correct_output(capsys):
    """
    Test that the start() method of QueryNotifyPrint prints the correct start message.
    It verifies the output contains the expected title, the given username and ends with 'on:'.
    """
    notifier = QueryNotifyPrint(verbose=False, print_all=True, browse=False)
    test_username = "testuser"
    notifier.start(test_username)
    output = capsys.readouterr().out
    ansi_escape = re.compile("\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])")
    plain_output = ansi_escape.sub("", output)
    assert (
        "Checking username" in plain_output
    ), "The start message should contain 'Checking username'"
    assert (
        test_username in plain_output
    ), "The username should be included in the start message"
    assert "on:" in plain_output, "The start message should end with 'on:'"


def test_update_available_no_prints_nothing(capsys):
    """
    Test that the update method for an AVAILABLE query result prints no output
    when print_all is set to False.
    """
    dummy_result = DummyQueryResult(
        status=QueryStatus.AVAILABLE,
        site_name="dummy_no_print",
        query_time=0.001,
        site_url_user="http://dummy.no.print",
        context="irrelevant",
    )
    notifier = QueryNotifyPrint(verbose=True, print_all=False, browse=False)
    notifier.update(dummy_result)
    captured_output = capsys.readouterr().out
    assert (
        captured_output == ""
    ), "No output should be printed when print_all is False for AVAILABLE status."


def test_finish_with_multiple_claimed_results(capsys):
    """
    Test that finish() correctly reports the number of CLAIMED results when multiple updates
    have been performed. The global counter (globvar) is reset before the test. Two update()
    calls with a CLAIMED status increment the counter, and finish() calls countResults() once
    more. The expected output is that finish() reports 2 results.
    """
    notify_mod.globvar = 0
    dummy_result = DummyQueryResult(
        status=QueryStatus.CLAIMED,
        site_name="dummy_multiple",
        query_time=0.004,
        site_url_user="http://dummymultiple.com",
    )
    notifier = QueryNotifyPrint(verbose=True, print_all=True, browse=False)
    notifier.update(dummy_result)
    notifier.update(dummy_result)
    notifier.finish()
    captured = capsys.readouterr().out
    plain_output = re.sub("\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])", "", captured)
    assert "2 results" in plain_output, "Finish output should indicate 2 results."


def test_str_method_returns_query_result():
    """
    Test that the __str__ method of QueryNotifyPrint returns the string representation of the query result.
    The test sets a dummy query result on the notifier and checks if str(notifier) equals str(dummy_result).
    """
    dummy_result = DummyQueryResult(
        status=QueryStatus.CLAIMED,
        site_name="test_site",
        query_time=0.005,
        site_url_user="http://test.com",
    )
    notifier = QueryNotifyPrint(verbose=True, print_all=True, browse=False)
    notifier.update(dummy_result)
    result_str = str(notifier)
    expected_str = str(dummy_result)
    assert (
        result_str == expected_str
    ), f"Expected __str__ to return '{expected_str}' but got '{result_str}'"
