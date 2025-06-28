from typing import List, Optional  # Needed in Python 3.7 & 3.8
from quart import (
    Blueprint, Quart,
    redirect, render_template, request, session, url_for,
)
from quart_session import Session
from .pallet import PalletAuth


class Auth(PalletAuth):
    """A long-live identity auth helper for a Quart web project."""
    _Blueprint = Blueprint
    _Session = Session
    _redirect = redirect
    _url_for = url_for

    def __init__(
        self,
        app: Optional[Quart],
        *args,
        post_logout_view: Optional[callable] = None,
        **kwargs,
    ):
        """Create an identity helper for a web application.

        :param Quart app:
            It can be a Quart app instance, or ``None``.

            1. If your app object is globally available, you may pass it in here.
               Usage::

                # In your app.py
                app = Quart(__name__)
                auth = Auth(app, authority=..., client_id=..., ...)

            2. But if you are using `Application Factory pattern
            <https://flask.palletsprojects.com/en/latest/patterns/appfactories/>`_,
            your app is not available globally, so you need to pass ``None`` here,
            and call :func:`Auth.init_app()` later,
            inside or after your app factory function. Usage::

                # In your auth.py
                auth = Auth(app=None, authority=..., client_id=..., ...)

                # In your other blueprints or modules
                from auth import auth

                bp = Blueprint("my_blueprint", __name__)

                @bp.route("/")
                @auth.login_required
                async def my_view(*, context):
                    ...

                # In your app.py
                from auth import auth
                import my_blueprint
                def build_app():
                    app = Quart(__name__)
                    auth.init_app(app)
                    app.register_blueprint(my_blueprint.bp)
                    return app

                app = build_app()

        :param callable post_logout_view:
            Optional.
            If not provided, the user will be redirected to the root URL of the app.
            If provided, it shall be the view (which is a function)
            that will be redirected to, after the user has logged out.

        It also passes extra parameters to :class:`identity.pallet.PalletAuth`.
        """
        self._request = request  # Not available during class definition
        self._session = session  # Not available during class definition
        self._post_logout_view = post_logout_view
        super(Auth, self).__init__(app, *args, **kwargs)

    async def _render_auth_error(self, *, error, error_description=None):
        return await render_template(
            f"{self._endpoint_prefix}/auth_error.html",
            error=error,
            error_description=error_description,
            reset_password_url=self._get_reset_password_url(),
            )

    async def login(
        self,
        *,
        next_link: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ):
        config_error = self._get_configuration_error()
        if config_error:
            return await self._render_auth_error(
                error="configuration_error", error_description=config_error)
        assert self._auth, "_auth should have been initialized"  # And mypy needs this
        log_in_result = self._auth.log_in(
            scopes=scopes,  # Have user consent to scopes (if any) during log-in
            redirect_uri=self._redirect_uri,
            prompt=self._prompt,  # self._prompt was defined in parent class
            next_link=next_link,
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

    def login_required(  # Named after Django's login_required
        self,
        function=None,
        /,  # Requires Python 3.8+
        *,
        scopes: Optional[List[str]] = None,
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
        return super(Auth, self).login_required(function, scopes=scopes)
