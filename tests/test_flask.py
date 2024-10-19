import shutil
from unittest.mock import patch, Mock

import pytest
from flask import Flask

from identity.flask import Auth


@pytest.fixture()
def app():  # https://flask.palletsprojects.com/en/3.0.x/testing/
    app = Flask(__name__)
    app.config.update({
        "APPLICATION_ROOT": "/app_root",  # Mimicking app with explicit root
        "SESSION_TYPE": "filesystem",  # Required for Flask-session,
            # see also https://stackoverflow.com/questions/26080872
    })
    yield app
    shutil.rmtree("flask_session")  # clean up

@pytest.fixture()
def auth(app):
    return Auth(
        app,
        client_id="fake",
        redirect_uri="http://localhost:5000/redirect",  # To use auth code flow
        oidc_authority="https://example.com/foo",
    )

def test_logout(app, auth):
    with patch.object(auth._auth, "_get_oidc_config", new=Mock(return_value={
        "end_session_endpoint": "https://example.com/end_session",
    })):
        with app.test_request_context("/", method="GET"):
            homepage = "http://localhost/app_root"
            assert homepage in auth.logout().get_data(as_text=True), (
                "The homepage should be in the logout URL. There was a bug in 0.9.0.")

@patch("msal.authority.tenant_discovery", new=Mock(return_value={
    "authorization_endpoint": "https://example.com/placeholder",
    "token_endpoint": "https://example.com/placeholder",
    }))
def test_login(app, auth):

    @app.route("/path")
    @auth.login_required
    def dummy_view():
        return "content visible after login"

    with app.test_request_context("/path", method="GET"):
        should_find_template = "login() should have template to render"
        assert auth._client_id in auth.login(), should_find_template
        with app.test_client() as client:
            result = client.get("/path?foo=bar")
            assert auth._client_id in str(result.data), should_find_template
            from flask import session  # It is different than auth._auth._session
            assert session.get("_auth_flow", {}).get("identity.web.next_link") == (
                "http://localhost/app_root/path?foo=bar"  # The full url
                ), "Next path should honor APPLICATION_ROOT"

