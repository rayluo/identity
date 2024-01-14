# pytest requires at least one test case to run
import pytest
from identity.django import _parse_redirect_uri

def test_parse_redirect_uri():
    with pytest.raises(ValueError):
        _parse_redirect_uri("https://example.com")
    with pytest.raises(ValueError):
        _parse_redirect_uri("https://example.com/")
    assert _parse_redirect_uri("https://example.com/x") == ("", "x")
    with pytest.raises(ValueError):
        _parse_redirect_uri("https://example.com/x/")
    assert _parse_redirect_uri("https://example.com/x/y") == ("x/", "y")
    assert _parse_redirect_uri("https://example.com/x/y/z") == ("x/y/", "z")
