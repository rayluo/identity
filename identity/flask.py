from typing import List, Optional  # Needed in Python 3.7 & 3.8
from flask import (
    Blueprint, Flask,
    redirect, render_template, request, session, url_for,
)
from flask_session import Session
from .pallet import PalletAuth


class Auth(PalletAuth):
    """A long-live identity auth helper for a Flask web project."""
    _Blueprint = Blueprint
    _Session = Session
    _redirect = redirect
    _url_for = url_for

    def __init__(
        self,
        app: Optional[Flask],
        *args,
        post_logout_view: Optional[callable] = None,
        **kwargs,
    ):
        """Initialize the Auth class for a Flask web application.

        :param Flask app:
            It can be a Flask app instance, or ``None``.

            1. If your app object is globally available, you may pass it in here.
               Usage::

                # In your app.py
                app = Flask(__name__)
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
                def my_view(*, context):
                    ...

                # In your app.py
                from auth import auth
                import my_blueprint
                def build_app():
                    app = Flask(__name__)
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

    def _render_auth_error(  # type: ignore[override]
        self, *, error, error_description=None,
    ) -> str:
        return render_template(
            f"{self._endpoint_prefix}/auth_error.html",
            error=error,
            error_description=error_description,
            reset_password_url=self._get_reset_password_url(),
            )

    def login(
        self,
        *,
        next_link: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> str:
        config_error = self._get_configuration_error()
        if config_error:
            return self._render_auth_error(
                error="configuration_error", error_description=config_error)
        assert self._auth, "_auth should have been initialized"  # And mypy needs this
        log_in_result: dict = self._auth.log_in(
            scopes=scopes,  # Have user consent to scopes (if any) during log-in
            redirect_uri=self._redirect_uri,
            prompt=self._prompt,  # self._prompt was defined in parent class
            next_link=next_link,
            )
        if "error" in log_in_result:
            return self._render_auth_error(
                error=log_in_result["error"],
                error_description=log_in_result.get("error_description"),
                )
        return render_template("identity/login.html", **dict(
            log_in_result,
            reset_password_url=self._get_reset_password_url(),
            auth_response_url=url_for(f"{self._endpoint_prefix}.auth_response"),
            ))

    def auth_response(self):
        result = self._auth.complete_log_in(request.args)
        if "error" in result:
            return self._render_auth_error(
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
            def index(*, context):
                return render_template(
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
                def call_an_api(*, context):
                    api_result = requests.get(  # Use access token to call an api
                        "https://example.com/endpoint",
                        headers={'Authorization': 'Bearer ' + context['access_token']},
                        timeout=30,
                    )
                    ...
        """
        return super(Auth, self).login_required(function, scopes=scopes)
