from functools import partial, wraps
from html import escape
import logging
import os
from typing import List  # Needed in Python 3.7 & 3.8
from urllib.parse import urlparse
import warnings

from django.shortcuts import redirect, render
from django.urls import include, path, reverse

from .web import Auth as _Auth


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

class Auth(object):

    def __init__(
        self,
        client_id: str,
        *,
        client_credential=None,
        redirect_uri: str=None,
        scopes: List[str]=None,
        authority: str=None,

        # We end up accepting Microsoft Entra ID B2C parameters rather than generic urls
        # because it is troublesome to build those urls in settings.py or templates
        b2c_tenant_name: str=None,
        b2c_signup_signin_user_flow: str=None,
        b2c_edit_profile_user_flow: str=None,
        b2c_reset_password_user_flow: str=None,
    ):
        """Create an identity helper for a Django web project.

        This instance is expected to be long-lived with the web project.

        :param str client_id:
            The client_id of your web application, issued by its authority.

        :param str client_credential:
            It is somtimes a string.
            The actual format is decided by the underlying auth library. TBD.

        :param str redirect_uri:
            This will be used to mount your project's auth views accordingly.

            For example, if your input here is "https://example.com/x/y/z/redirect",
            then your project's redirect page will be mounted at "/x/y/z/redirect",
            login page will be at "/x/y/z/login",
            and logout page will be at "/x/y/z/logout".

            Afterwards, all you need to do is to insert ``auth.urlpattern`` into
            your project's ``urlpatterns`` list in ``your_project/urls.py``.

        :param list[str] scopes:
            Deprecated. Use @login_required(..., scopes=[...]) instead.

        :param str authority:
            The authority which your application registers with.
            For example, ``https://example.com/foo``.
            This is a required parameter unless you the following B2C parameters.

        :param str b2c_tenant_name:
            The tenant name of your Microsoft Entra ID tenant, such as "contoso".
            Required if your project is using Microsoft Entra ID B2C.

        :param str b2c_signup_signin_user_flow:
            The name of your Microsoft Entra ID tenant's sign-in flow,
            such as "B2C_1_signupsignin1".
            Required if your project is using Microsoft Entra ID B2C.

        :param str b2c_edit_profile_user_flow:
            The name of your Microsoft Entra ID tenant's edit-profile flow,
            such as "B2C_1_profile_editing".
            Optional.

        :param str b2c_edit_profile_user_flow:
            The name of your Microsoft Entra ID tenant's reset-password flow,
            such as "B2C_1_reset_password".
            Optional.

        """
        self._client_id = client_id
        self._client_credential = client_credential
        if scopes:
            warnings.warn(
                "The 'scopes' parameter is deprecated. "
                "Use @login_required(..., scopes=[...]) instead",
                DeprecationWarning)
        self._http_cache = {}  # All subsequent _Auth instances will share this

        self._redirect_uri = redirect_uri
        route, self._redirect_view = _parse_redirect_uri(redirect_uri)
        self.urlpattern = path(route, include([
            # Note: path(..., view, ...) does not accept classmethod
            path('login', self.login),
            path('logout', self.logout, name=f"{__name__}.logout"),
            path(
                self._redirect_view or 'auth_response',  # The latter is used by device code flow
                self.auth_response,
            ),
        ]))

        # Note: We do not use overload, because we want to allow the caller to
        # have only one code path that relay in all the optional parameters.
        if b2c_tenant_name and b2c_signup_signin_user_flow:
            b2c_authority_template = (  # TODO: Support custom domain
                "https://{tenant}.b2clogin.com/{tenant}.onmicrosoft.com/{user_flow}")
            self._authority = b2c_authority_template.format(
                tenant=b2c_tenant_name,
                user_flow=b2c_signup_signin_user_flow,
                )
            self._edit_profile_auth = _Auth(
                session={},
                authority=b2c_authority_template.format(
                    tenant=b2c_tenant_name,
                    user_flow=b2c_edit_profile_user_flow,
                    ),
                client_id=client_id,
                ) if b2c_edit_profile_user_flow else None
            self._reset_password_auth = _Auth(
                session={},
                authority=b2c_authority_template.format(
                    tenant=b2c_tenant_name,
                    user_flow=b2c_reset_password_user_flow,
                    ),
                client_id=client_id,
                ) if b2c_reset_password_user_flow else None
        else:
            self._authority = authority
            self._edit_profile_auth = None
            self._reset_password_auth = None
        if not self._authority:
            logger.error(  # Do not raise exception, because
                # we want to render a nice error page later during login,
                # which is a better developer experience especially for deployment
                "Either authority or b2c_tenant_name and b2c_signup_signin_user_flow "
                "must be provided")

    def _build_auth(self, request):
        return _Auth(
            session=request.session,
            authority=self._authority,
            client_id=self._client_id,
            client_credential=self._client_credential,
            http_cache=self._http_cache,
            )

    def _get_reset_password_url(self, request):
        return self._reset_password_auth.log_in(
            redirect_uri=request.build_absolute_uri(self._redirect_view),
            state=self._reset_password_auth.__STATE_NO_OP,
            )["auth_uri"] if self._reset_password_auth and self._redirect_view else None

    def get_edit_profile_url(self, request):
        """A helper to get the URL for Microsoft Entra B2C's edit profile page.

        You can pass this URL to your template and render it there.
        """
        return self._edit_profile_auth.log_in(
            redirect_uri=request.build_absolute_uri(self._redirect_view),
            state=self._edit_profile_auth.__STATE_NO_OP,
            )["auth_uri"] if self._edit_profile_auth and self._redirect_view else None

    def login(
        self,
        request,
        next_link:str = None,  # Obtain the next_link from the app developer,
            # NOT from query string which could become an open redirect vulnerability.
        scopes: List[str]=None,
    ):
        # The login view.
        # App developer could redirect to the login page from inside a view,
        # by calling ``return redirect(auth.login)``.
        # But a better approach is to use the ``@login_required`` decorator
        # which will implicitly call this login view when needed.
        if not (self._client_id and self._authority):
            return self._render_auth_error(
                request,
                error="configuration_error",
                error_description="""Almost there. Did you forget to setup
(1) authority, or the b2c_tenant_name and b2c_signup_signin_user_flow pair
(2) client_id
?""",
                )
        redirect_uri = request.build_absolute_uri(
            self._redirect_view) if self._redirect_view else None
        if redirect_uri != self._redirect_uri:
            logger.warning(
                "redirect_uri mismatch: configured = %s, calculated = %s",
                self._redirect_uri, redirect_uri)
        log_in_result = self._build_auth(request).log_in(
            scopes=scopes,  # Have user consent to scopes (if any) during log-in
            redirect_uri=redirect_uri,  # Optional. If present, this absolute URL must match your app's redirect_uri registered in Azure Portal
            prompt="select_account",  # Optional. More values defined in  https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest
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
            reset_password_url=self._get_reset_password_url(request),
            auth_response_url=reverse(self.auth_response),
            ))

    def _render_auth_error(self, request, error, error_description=None):
        return render(request, "identity/auth_error.html", dict(
            # Use flat data types so that the template can be as simple as possible
            error=escape(error),
            error_description=escape(error_description or ""),
            reset_password_url=self._get_reset_password_url(request),
            ))

    def auth_response(self, request):
        # The auth_response view. You should not need to call this view directly.
        result = self._build_auth(request).complete_log_in(request.GET)
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
        return redirect(
            self._build_auth(request).log_out(request.build_absolute_uri("/")))

    def get_user(self, request):
        ""  # Nullify the following docstring, because we recommend using login_required()
        """Get the logged-in user of the request.

        :param request: The request object of the current view.

        :return:
            The user object which is a dict of claims,
            or None if the user is not logged in.
        """
        return self._build_auth(request).get_user()

    def get_token_for_user(self, request, scopes: List[str]):
        ""  # Nullify the following docstring, because we recommend using login_required()
        """Get access token for the current user, with specified scopes.

        :param list scopes:
            A list of scopes that your app will need to use.

        :return: A dict representing the json response from identity provider.

            - A successful response would contain "access_token" key,
            - An error response would contain "error" and usually "error_description".

            See also `OAuth2 specs <https://www.rfc-editor.org/rfc/rfc6749#section-5>`_.
        """
        return self._build_auth(request).get_token_for_user(scopes)

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
                    ).json()  # Here we assume the response format is json
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
            auth = self._build_auth(request)
            user = auth.get_user()
            if user:
                if scopes:
                    result = auth.get_token_for_user(scopes)
                    if isinstance(result, dict) and "access_token" in result:
                        context = dict(
                            user=user,
                            # https://datatracker.ietf.org/doc/html/rfc6749#section-5.1
                            access_token=result["access_token"],
                            token_type=result.get("token_type", "Bearer"),
                            expires_in=result.get("expires_in", 300),
                            refresh_token=result.get("refresh_token"),
                        )
                        if result.get("scope"):
                            context["scopes"] = result["scope"].split()
                    else:
                        pass  # Token request failed. So we set no context.
                else:
                    context = {"user": user}
                if context:
                    try:
                        return function(request, *args, context=context, **kwargs)
                    except TypeError:
                        if scopes:
                            raise
                        warnings.warn(
                            "The '@login_required(...)' decorated view should accept "
                            "a keyword argument named 'context'. For example, "
                            "def my_view(request, *, context): ...",
                            DeprecationWarning)
                        return function(request, *args, **kwargs)
            # Save an http 302 by calling self.login(request) instead of redirect(self.login)
            return self.login(
                request,
                next_link=request.get_full_path(),
                scopes=scopes,
                )
        return wrapper

