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

