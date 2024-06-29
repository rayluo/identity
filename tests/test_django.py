import os
from unittest import mock

import pytest

from identity.django import _parse_redirect_uri, Auth


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

def test_configuration_errors_should_be_delivered_to_log_in():
    auth = Auth(None)  # No exception raised
    with mock.patch.object(auth, "_render_auth_error") as mock_render_auth_error:
        auth.login(object())
        mock_render_auth_error.assert_called_once_with(
            mock.ANY, error="configuration_error", error_description=mock.ANY)

# I don't know how to create a dummy Django app on-the-fly, here we do this instead
def test_the_installed_package_contains_builtin_templates():
    import identity
    templates_needed = {"login.html", "auth_error.html"}
    templates_found = set()
    for path in identity.__path__:
        for t in templates_needed:
            if os.path.exists(os.path.join(path, "templates", "identity", t)):
                templates_found.add(t)
    assert templates_needed == templates_found

