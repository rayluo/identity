import msal
import pytest
from quart import Quart
from identity.quart import Auth


@pytest.mark.asyncio
async def test_login(monkeypatch):
    app = Quart(__name__)
    app.config["SESSION_TYPE"] = "redis"
    auth = Auth(
        app,
        authority="https://login.microsoftonline.com/123",
        client_id="fake",
        client_credential="fake",
        redirect_uri="http://localhost:5000/auth_response",
    )

    monkeypatch.setattr(
        msal.authority,
        "tenant_discovery",
        lambda *args, **kwargs: {
            "authorization_endpoint": "https://login.microsoftonline.com/123/oauth2/v2.0/authorize",
            "token_endpoint": "https://login.microsoftonline.com/123/oauth2/v2.0/token",
        },
    )

    async with app.test_request_context("/", method="GET"):
        rendered_template = await auth.login()

        assert "https://login.microsoftonline.com/123/oauth2/v2.0/authorize" in rendered_template
