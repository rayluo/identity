from unittest.mock import patch, Mock

from flask import Flask

from identity.flask import Auth


def test_logout():
    app = Flask(__name__)
    app.config["SESSION_TYPE"] = "filesystem"  # Required for Flask-session,
        # see also https://stackoverflow.com/questions/26080872
    auth = Auth(app, client_id="fake")
    with app.test_request_context("/", method="GET"):
        assert auth._request.host_url in auth.logout().get_data(as_text=True), (
            "The host_url should be in the logout URL. There was a bug in 0.9.0.")

@patch("msal.authority.tenant_discovery", new=Mock(return_value={
    "authorization_endpoint": "https://example.com/placeholder",
    "token_endpoint": "https://example.com/placeholder",
    }))
def test_login_should_locate_its_template():
    app = Flask(__name__)
    app.config["SESSION_TYPE"] = "filesystem"  # Required for Flask-session,
        # see also https://stackoverflow.com/questions/26080872
    client_id = str(hash(app))
    auth = Auth(
        app,
        client_id=client_id,
        redirect_uri="http://localhost:5000/redirect",  # To use auth code flow
        oidc_authority="https://example.com/foo",
        )
    with app.test_request_context("/", method="GET"):
        assert client_id in auth.login()  # Proper template output contains client_id

