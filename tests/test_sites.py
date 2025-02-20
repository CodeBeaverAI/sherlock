import json
import pytest
import secrets
from pathlib import (
    Path,
)
from sherlock_project import (
    sites,
)


def test_invalid_file_extension(tmp_path):
    """
    Test that SitesInformation raises FileNotFoundError when provided a file
    with an invalid extension (i.e., not ending with '.json').
    """
    invalid_file = tmp_path / "data.txt"
    file_content = {
        "testsite": {
            "urlMain": "http://example.com",
            "url": "http://example.com/{}",
            "username_claimed": "exists",
            "isNSFW": False,
        }
    }
    invalid_file.write_text(json.dumps(file_content))
    with pytest.raises(FileNotFoundError, match="Incorrect JSON file extension"):
        sites.SitesInformation(str(invalid_file))


def test_remove_nsfw_and_site_name_list(tmp_path):
    """
    Test SitesInformation's remove_nsfw_sites method with and without
    exceptions, and validate that site_name_list returns a sorted list.
    """
    file_path = tmp_path / "data.json"
    site_data = {
        "safe_site": {
            "urlMain": "http://safesite.com",
            "url": "http://safesite.com/{}",
            "username_claimed": "claimed",
            "isNSFW": False,
        },
        "unsafe_site": {
            "urlMain": "http://unsafesite.com",
            "url": "http://unsafesite.com/{}",
            "username_claimed": "claimed",
            "isNSFW": True,
        },
    }
    file_path.write_text(json.dumps(site_data))
    sites_info = sites.SitesInformation(str(file_path))
    assert len(sites_info) == 2
    sites_info.remove_nsfw_sites()
    assert len(sites_info) == 1
    remaining_site_names = [site.name for site in sites_info]
    assert "safe_site" in remaining_site_names
    assert "unsafe_site" not in remaining_site_names
    sites_info_exception = sites.SitesInformation(str(file_path))
    sites_info_exception.remove_nsfw_sites(do_not_remove=["unsafe_site"])
    assert len(sites_info_exception) == 2
    all_site_names = [site.name for site in sites_info_exception]
    assert "safe_site" in all_site_names
    assert "unsafe_site" in all_site_names
    name_list = sites_info_exception.site_name_list()
    assert name_list == sorted(name_list, key=str.lower)


def test_remote_url_bad_status(monkeypatch):
    """
    Test that when SitesInformation loads data from a remote URL that returns a non-200
    status code, it raises a FileNotFoundError indicating a bad response.
    """

    class FakeResponse:

        def __init__(self, status_code):
            self.status_code = status_code

        def json(self):
            return {}

    def fake_get(*args, **kwargs):
        return FakeResponse(404)

    monkeypatch.setattr(sites.requests, "get", fake_get)
    with pytest.raises(
        FileNotFoundError, match="Bad response while accessing data file URL"
    ):
        sites.SitesInformation("http://example.com/data.json")


def test_invalid_site_structure(tmp_path, capsys):
    """
    Test that SitesInformation skips a site with an invalid structure (non-dictionary)
    and prints an error message when encountering a TypeError.
    """
    file_path = tmp_path / "data.json"
    site_data = {
        "invalid_site": "not_a_dict",
        "valid_site": {
            "urlMain": "http://valid.com",
            "url": "http://valid.com/{}",
            "username_claimed": "claimed",
            "isNSFW": False,
        },
    }
    file_path.write_text(json.dumps(site_data))
    sites_info = sites.SitesInformation(str(file_path))
    site_names = [site.name for site in sites_info]
    assert "valid_site" in site_names
    assert "invalid_site" not in site_names
    captured = capsys.readouterr().out
    assert "Encountered TypeError parsing json contents" in captured


def test_remote_valid_data(monkeypatch):
    """
    Test that SitesInformation correctly loads valid remote JSON data and that
    the SiteInformation __str__ method returns the expected string.
    This simulates a valid remote URL by monkeypatching requests.get.
    """

    class FakeResponse:

        def __init__(self, json_data, status_code=200):
            self._json_data = json_data
            self.status_code = status_code

        def json(self):
            return self._json_data

    def fake_get(*args, **kwargs):
        fake_data = {
            "example_site": {
                "urlMain": "http://example.com",
                "url": "http://example.com/{}",
                "username_claimed": "claimed",
                "isNSFW": False,
            }
        }
        return FakeResponse(fake_data, status_code=200)

    monkeypatch.setattr(sites.requests, "get", fake_get)
    sites_info = sites.SitesInformation("http://fakeurl.com/data.json")
    assert len(sites_info) == 1
    site = next(iter(sites_info))
    expected_str = "example_site (http://example.com)"
    assert str(site) == expected_str


def test_missing_required_attribute(tmp_path):
    """
    Test that SitesInformation raises ValueError when a required attribute
    (e.g., "urlMain") is missing from a site's data in the JSON file.
    This ensures that the code properly detects incomplete site data.
    """
    file_path = tmp_path / "data.json"
    site_data = {
        "incomplete_site": {
            "url": "http://incomplete.com/{}",
            "username_claimed": "claimed",
            "isNSFW": False,
        }
    }
    file_path.write_text(json.dumps(site_data))
    with pytest.raises(ValueError, match="Missing attribute"):
        sites.SitesInformation(str(file_path))


def test_local_file_not_found(tmp_path):
    """
    Test that SitesInformation raises a FileNotFoundError when provided a path to a non-existent local JSON file.
    """
    non_existent_file = tmp_path / "non_existent.json"
    with pytest.raises(
        FileNotFoundError, match="Problem while attempting to access data file"
    ):
        sites.SitesInformation(str(non_existent_file))


def test_invalid_json_parsing_local(tmp_path):
    """
    Test that SitesInformation raises ValueError when the local JSON file contains invalid JSON.
    This ensures that the JSON parse errors are correctly handled.
    """
    file_path = tmp_path / "invalid.json"
    file_path.write_text("This is not valid JSON")
    with pytest.raises(ValueError, match="Problem parsing json contents"):
        sites.SitesInformation(str(file_path))


def test_schema_key_removed(tmp_path):
    """
    Test that SitesInformation correctly removes the "$schema" key from the JSON file,
    ensuring that it does not attempt to create a site from that entry.
    """
    file_path = tmp_path / "data.json"
    site_data = {
        "$schema": "https://example.com/schema.json",
        "test_site": {
            "urlMain": "http://testsite.com",
            "url": "http://testsite.com/{}",
            "username_claimed": "claimed",
            "isNSFW": False,
        },
    }
    file_path.write_text(json.dumps(site_data))
    sites_info = sites.SitesInformation(str(file_path))
    assert len(sites_info) == 1
    site_names = [site.name for site in sites_info]
    assert "test_site" in site_names


def test_site_information_username_unclaimed_override():
    """
    Test that SiteInformation always generates a new secret token for username_unclaimed,
    even if a value is provided through the constructor.
    """
    provided_token = "provided_value"
    site_dict = {
        "urlMain": "http://override.com",
        "url": "http://override.com/{}",
        "username_claimed": "claimed",
        "isNSFW": False,
    }
    site_info = sites.SiteInformation(
        name="override_test",
        url_home=site_dict["urlMain"],
        url_username_format=site_dict["url"],
        username_claimed=site_dict["username_claimed"],
        information=site_dict,
        is_nsfw=site_dict["isNSFW"],
        username_unclaimed=provided_token,
    )
    assert (
        site_info.username_unclaimed != provided_token
    ), "username_unclaimed should be overridden by a new secret token."
    assert isinstance(site_info.username_unclaimed, str)
    assert len(site_info.username_unclaimed) > len(provided_token)


def test_remote_invalid_json(monkeypatch):
    """
    Test that SitesInformation raises a ValueError when a remote URL returns invalid JSON.
    This simulates the scenario where response.json() raises an exception.
    """

    class FakeResponse:

        def __init__(self, status_code=200):
            self.status_code = status_code

        def json(self):
            raise ValueError("Invalid JSON")

    def fake_get(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(sites.requests, "get", fake_get)
    with pytest.raises(ValueError, match="Problem parsing json contents at"):
        sites.SitesInformation("http://fakeurl.com/data_invalid.json")
