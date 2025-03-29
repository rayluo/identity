from abc import abstractmethod
from functools import partial, wraps
from inspect import iscoroutinefunction
import logging
import os
from typing import List, Optional  # Needed in Python 3.7 & 3.8
from urllib.parse import urlparse
from .web import WebFrameworkAuth, Auth


logger = logging.getLogger(__name__)


class PalletAuth(WebFrameworkAuth):  # A common base class for Flask and Quart
    _endpoint_prefix = "identity"  # A convention to match the template's folder name
    _auth: Optional[Auth] = None  # None means not initialized yet

    def __init__(self, app, *args, **kwargs):
        if not (
            self._Blueprint and self._Session and self._redirect
            and getattr(self, "_session", None) is not None
            and getattr(self, "_request", None) is not None
        ):
            raise RuntimeError(
                "Subclass must provide "
                "_Blueprint, _Session, _redirect, _session, and _request.")
        super(PalletAuth, self).__init__(*args, **kwargs)
        self._bp = bp = self._Blueprint(
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
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the auth helper with your app instance."""  # Note:
            # This doc string will be shared by Flask and Quart,
            # so we use a vague "your app" without mentioning Flask or Quart here.
        self._Session(app)
        # "Don’t do self.app = app", see https://flask.palletsprojects.com/en/3.0.x/extensiondev/#the-extension-class-and-initialization
        app.register_blueprint(self._bp)
        self._auth = self._build_auth(self._session)

    def __getattribute__(self, name):
        # self._auth also doubles as a flag for initialization
        if name == "_auth" and not super(PalletAuth, self).__getattribute__(name):
            # Can't use self._render_auth_error(...) for friendly error message
            # because bp has not been registered to the app yet
            raise RuntimeError(
                "You must call auth.init_app(app) before using "
                "@auth.login_required() or auth.logout() etc.")
        return super(PalletAuth, self).__getattribute__(name)

    def logout(self, post_logout_redirect_uri: Optional[str] = None):
        return self.__class__._redirect(  # self._redirect(...) won't work
            self._auth.log_out(post_logout_redirect_uri or self._request.url_root)
        )

    def login_required(  # Named after Django's login_required
        self,
        function=None,
        /,  # Requires Python 3.8+
        *,
        scopes: Optional[List[str]] = None,
    ):
        # With or without brackets. Inspired by https://stackoverflow.com/a/39335652/728675

        # Called with brackets, i.e. @login_required()
        if function is None:
            logger.debug(f"Called as @login_required(..., scopes={scopes})")
            return partial(
                self.login_required,
                scopes=scopes,
            )

        # Called without brackets, i.e. @login_required
        if iscoroutinefunction(function):  # For Quart
            @wraps(function)
            async def wrapper(*args, **kwargs):
                user = self._auth.get_user()
                context = self._login_required(self._auth, user, scopes)
                if context:
                    return await function(*args, context=context, **kwargs)
                # Save an http 302 by calling self.login(request) instead of redirect(self.login)
                return await self.login(next_link=self._request.url, scopes=scopes)
        else:  # For Flask
            @wraps(function)
            def wrapper(*args, **kwargs):
                user = self._auth.get_user()
                context = self._login_required(self._auth, user, scopes)
                if context:
                    return function(*args, context=context, **kwargs)
                # Save an http 302 by calling self.login(request) instead of redirect(self.login)
                return self.login(next_link=self._request.url, scopes=scopes)
        return wrapper

