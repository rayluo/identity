from functools import partial, wraps
import logging
import os
from typing import List, Optional  # Needed in Python 3.7 & 3.8
from urllib.parse import urlparse

from django.shortcuts import redirect, render
from django.urls import include, path, reverse

from .web import WebFrameworkAuth


logger = logging.getLogger(__name__)


def _parse_redirect_uri(redirect_uri):
    """Parse the redirect_uri into a tuple of (django_route, view)"""
    if redirect_uri:
        prefix, view = os.path.split(urlparse(redirect_uri).path)
        if not view:
            raise ValueError(
                'redirect_uri must contain a path which does not end with a "/"')
        route = prefix[1:] if prefix and prefix[0] == '/' else prefix
        if route:
            route += "/"
        return route, view
    else:
        return "", None

class Auth(WebFrameworkAuth):
    """A long-live identity auth helper for a Django web project.

    Afterwards, all you need to do is to insert ``auth.urlpattern`` into
    your project's ``urlpatterns`` list in ``your_project/urls.py``.
    """

    def __init__(
        self,
        *args,
        post_logout_view: Optional[callable] = None,
        prompt: Optional[str] = None,
        **kwargs,
    ):
        """Initialize the Auth class for a Django web application.

        :param callable post_logout_view:
            Optional.
            If not provided, the user will be redirected to the root URL of the app.

            If provided, it shall be the view (which is a function)
            that will be redirected to, after the user has logged out.
            For example, you will typically use this parameter like this::

                from . import public_views  # This module shall NOT import settings.AUTH
                auth = Auth(
                    ...,
                    post_logout_view=public_views.my_post_logout_view,
                )

            where ``my_post_logout_view`` is a Django view function.

        :param str prompt:
            Optional. The prompt parameter to be used during login.
            Valid values are defined in
            `OpenID Connect Core spec <https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest>`_.

            Starting from Identity 0.11.0,
            the default value is changed from ``"select_account"`` to ``None``.
            ``None`` means no prompt will be sent in the authentication request,
            not even string ``"none"``. The Identity Server will decide whether to prompt.
        """
        self._prompt = prompt
        super(Auth, self).__init__(*args, **kwargs)
        route, redirect_view = _parse_redirect_uri(self._redirect_uri)
        self.urlpattern = path(route, include([
            # Note: path(..., view, ...) does not accept classmethod
            path('login', self.login),
            path('logout', self.logout, name=f"identity.logout"),
            path(
                redirect_view or 'auth_response',  # The latter is used by device code flow
                self.auth_response,
            ),
        ]))
        self._post_logout_view = post_logout_view

    def login(
        self,
        request,
        next_link: Optional[str] = None,  # Obtain the next_link from the app developer,
            # NOT from query string which could become an open redirect vulnerability.
        scopes: Optional[List[str]] = None,
    ):
        # The login view.
        # App developer could redirect to the login page from inside a view,
        # by calling ``return redirect(auth.login)``.
        # But a better approach is to use the ``@login_required`` decorator
        # which will implicitly call this login view when needed.
        config_error = self._get_configuration_error()
        if config_error:
            return self._render_auth_error(
                request, error="configuration_error", error_description=config_error)
        log_in_result = self._build_auth(request.session).log_in(
            scopes=scopes,  # Have user consent to scopes (if any) during log-in
            redirect_uri=self._redirect_uri,  # Optional. If present, this absolute URL must match your app's redirect_uri registered in Azure Portal
            prompt=self._prompt,  # Optional. More values defined in  https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest
            next_link=next_link,
            )
        if "error" in log_in_result:
            return self._render_auth_error(
                request,
                error=log_in_result["error"],
                error_description=log_in_result.get("error_description"),
                )
        return render(request, "identity/login.html", dict(
            log_in_result,
            reset_password_url=self._get_reset_password_url(),
            auth_response_url=reverse(self.auth_response),
            ))

    def _render_auth_error(self, request, *, error, error_description=None):
        return render(request, "identity/auth_error.html", dict(
            # Use flat data types so that the template can be as simple as possible
            error=error,
            error_description=error_description or "",
            reset_password_url=self._get_reset_password_url(),
            ))

    def auth_response(self, request):
        # The auth_response view. You should not need to call this view directly.
        result = self._build_auth(request.session).complete_log_in(request.GET)
        if "error" in result:
            return self._render_auth_error(
                request,
                error=result["error"],
                error_description=result.get("error_description"),
                )
        return redirect(
            result.get("next_link")
            or "/")  # Use a relative URL rather than a hard-coded view name

    def logout(self, request):
        """The logout view.

        The logout url is also available with the name "identity.django.logout".
        So you can use ``{% url "identity.django.logout" %}`` to get the url
        from inside a template.
        """
        return redirect(self._build_auth(request.session).log_out(request.build_absolute_uri(
            reverse(self._post_logout_view) if self._post_logout_view else "/"
        )))

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

            @settings.AUTH.login_required
            def my_view(request, *, context):
                return render(request, 'index.html', dict(
                    user=context["user"],  # User is guaranteed to be present
                        # because we decorated this view with @login_required
                    ))

        :param list[str] scopes:
            A list of scopes that your app will need to use.
            When present, the context will also contain an "access_token",
            "token_type", and likely "expires_in" and "refresh_token".

            Usage::

                @settings.AUTH.login_required(scopes=["scope1", "scope2"])
                def my_view2(request, *, context):
                    api_result = requests.get(  # Use access token to call an api
                        "https://example.com/endpoint",
                        headers={'Authorization': 'Bearer ' + context['access_token']},
                        timeout=30,
                    )
                    ...
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
        def wrapper(request, *args, **kwargs):
            auth = self._build_auth(request.session)
            user = auth.get_user()
            context = self._login_required(auth, user, scopes)
            if context:
                try:
                    return function(request, *args, context=context, **kwargs)
                except TypeError as exp:
                    if "context" in str(exp):
                        raise RuntimeError(
                            "Since identity 0.6.0, the '@login_required(...)' decorated "
                            "view should accept a keyword argument named 'context'. "
                            "For example, def my_view(request, *, context): ...") from exp
                    raise
            # Save an http 302 by calling self.login(request) instead of redirect(self.login)
            return self.login(
                request,
                next_link=request.get_full_path(),
                scopes=scopes,
                )
        return wrapper
