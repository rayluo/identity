from functools import partial, wraps
import logging
import os
from typing import List  # Needed in Python 3.7 & 3.8
from urllib.parse import urlparse

from quart import (
    Blueprint, Quart,
    redirect, render_template, request, session, url_for,
)
from quart_session import Session

from .web import WebFrameworkAuth


logger = logging.getLogger(__name__)


class Auth(WebFrameworkAuth):
    """A long-live identity auth helper for a Flask web project."""

    def __init__(self, app: Quart, *args, **kwargs):
        """Create an identity helper for a web application.

        :param Quart app:
            A Quart app instance. It will be used to register the routes.

        It also passes extra parameters to :class:`identity.web.WebFrameworkAuth`.
        """
        super(Auth, self).__init__(*args, **kwargs)
        Session(app)
        self._endpoint_prefix = "identity"  # A convention to match the template's folder name
        bp = Blueprint(
            self._endpoint_prefix,
            __name__,  # It decides blueprint resource folder
            template_folder='templates',
        )
        # Manually register the routes, since we cannot use @app or @bp on methods
        if self._redirect_uri:
            redirect_path = urlparse(self._redirect_uri).path
            bp.route(redirect_path)(self.auth_response)
            bp.route(
                f"{os.path.dirname(redirect_path)}/logout"  # Use it in template by url_for("identity.logout")
                )(self.logout)
        else:  # For Device Code Flow, we don't have a redirect_uri
            bp.route("/auth_response")(self.auth_response)
            bp.route("/logout")(self.logout)
        app.register_blueprint(bp)
        # "Don’t do self.app = app", see https://flask.palletsprojects.com/en/3.0.x/extensiondev/#the-extension-class-and-initialization
        self._auth = self._build_auth(session)

    async def _render_auth_error(self, *, error, error_description=None):
        return await render_template(
            f"{self._endpoint_prefix}/auth_error.html",
            error=error,
            error_description=error_description,
            reset_password_url=self._get_reset_password_url(),
            )

    async def login(self, *, next_link: str=None, scopes: List[str]=None):
        config_error = self._get_configuration_error()
        if config_error:
            return await self._render_auth_error(
                error="configuration_error", error_description=config_error)
        log_in_result = self._auth.log_in(
            scopes=scopes,  # Have user consent to scopes (if any) during log-in
            redirect_uri=self._redirect_uri,
            prompt="select_account",  # Optional. More values defined in  https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest
            )
        if "error" in log_in_result:
            return await self._render_auth_error(
                error=log_in_result["error"],
                error_description=log_in_result.get("error_description"),
                )
        return await render_template("identity/login.html", **dict(
            log_in_result,
            reset_password_url=self._get_reset_password_url(),
            auth_response_url=url_for(f"{self._endpoint_prefix}.auth_response"),
            ))

    async def auth_response(self):
        result = self._auth.complete_log_in(request.args)
        if "error" in result:
            return await self._render_auth_error(
                error=result["error"],
                error_description=result.get("error_description"),
                )
        return redirect(result.get("next_link") or "/")

    def logout(self):
        return redirect(self._auth.log_out(request.host_url))

    def login_required(  # Named after Django's login_required
        self,
        function=None,
        /,  # Requires Python 3.8+
        *,
        scopes: List[str]=None,
    ):
        """A decorator that ensures the user to be logged in,
        and optinoally also have consented to a list of scopes.

        A user not meeting the requirement(s) will be brought to the login page.
        For already logged-in user, the view will be called with a keyword argument
        named "context" which is a dict containing the user object.

        Usage::

            @app.route("/")
            @auth.login_required
            async def index(*, context):
                return await render_template(
                    'index.html',
                    user=context["user"],  # User is guaranteed to be present
                        # because we decorated this view with @login_required
                )

        :param list[str] scopes:
            A list of scopes that your app will need to use.
            When present, the context will also contain an "access_token",
            "token_type", and likely "expires_in" and "refresh_token".

            Usage::

                @app.route("/call_api")
                @auth.login_required(scopes=["scope1", "scope2"])
                async def call_api(*, context):
                    async with httpx.AsyncClient() as client:
                        api_result = await client.get(  # Use access token to call a web api
                            os.getenv("ENDPOINT"),
                            headers={'Authorization': 'Bearer ' + context['access_token']},
                        )
                    return await render_template('display.html', result=api_result)

        """
        # With or without brackets. Inspired by https://stackoverflow.com/a/39335652/728675

        # Called with brackets, i.e. @login_required()
        if function is None:
            logger.debug(f"Called as @login_required(..., scopes={scopes})")
            return partial(
                self.login_required,
                scopes=scopes,
            )

        # Called without brackets, i.e. @login_required
        @wraps(function)
        async def wrapper(*args, **kwargs):
            auth = self._auth  # In Flask, the entire app uses a singleton _auth
            user = auth.get_user()
            context = self._login_required(auth, user, scopes)
            if context:
                return await function(*args, context=context, **kwargs)
            # Save an http 302 by calling self.login(request) instead of redirect(self.login)
            return await self.login(
                next_link=request.path,  # https://flask.palletsprojects.com/en/3.0.x/api/#flask.Request.path
                scopes=scopes,
                )
        return wrapper

