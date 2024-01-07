from functools import partial, wraps
from html import escape
from typing import List  # Needed in Python 3.7 & 3.8

from django.shortcuts import redirect, render
from django.urls import path, reverse

from .web import Auth as _Auth


class Auth(object):
    _name_of_auth_response_view = f"{__name__}.auth_response"  # Presumably unique

    def __init__(
        self,
        client_id: str,
        *,
        client_credential=None,
        redirect_view: str=None,
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

        :param str redirect_view:
            This will be used as the last segment to form your project's redirect_uri.

            For example, if you provide an input here as "auth_response",
            and your Django project mounts this ``Auth`` object's ``urlpatterns``
            by ``path("prefix/", include(auth.urlpatterns))``,
            then the actual redirect_uri will become ``.../prefix/auth_response``
            which MUST match what you have registered for your web application.

            Typically, if your application uses a flat redirect_uri as
            ``https://example.com/auth_response``,
            your shall use an redirect_view value as ``auth_response``,
            and then mount it by ``path("", include(auth.urlpatterns))``.


        :param list[str] scopes:
            A list of strings representing the scopes used during login.

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
        if redirect_view and "/" in redirect_view:
            raise ValueError("redirect_view shall not contain slash")
        self._redirect_view = redirect_view
        self._scopes = scopes
        self.urlpatterns = [  # Note: path(..., view, ...) does not accept classmethod
            path('login', self.login),
            path('logout', self.logout),
            path(
                redirect_view or 'auth_response',  # The latter is used by device code flow
                self.auth_response,
                name=self._name_of_auth_response_view,
                ),
        ]
        self._http_cache = {}  # All subsequent _Auth instances will share this

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
            raise ValueError(
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
            redirect_uri=request.build_absolute_uri(self._redirect_view)
            )["auth_uri"] if self._reset_password_auth and self._redirect_view else None

    def get_edit_profile_url(self, request):
        return self._edit_profile_auth.log_in(
            redirect_uri=request.build_absolute_uri(self._redirect_view)
            )["auth_uri"] if self._edit_profile_auth and self._redirect_view else None

    def login(self, request):
        """The login view"""
        if not self._client_id:
            return self._render_auth_error(
                request,
                error="configuration_error",
                error_description="Did you forget to setup CLIENT_ID (and other configuration)?",
                )
        redirect_uri = request.build_absolute_uri(
            self._redirect_view) if self._redirect_view else None
        log_in_result = self._build_auth(request).log_in(
            scopes=self._scopes,  # Have user consent to scopes during log-in
            redirect_uri=redirect_uri,  # Optional. If present, this absolute URL must match your app's redirect_uri registered in Azure Portal
            prompt="select_account",  # Optional. More values defined in  https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest
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
            auth_response_url=reverse(self._name_of_auth_response_view),
            ))

    def _render_auth_error(self, request, error, error_description=None):
        return render(request, "identity/auth_error.html", dict(
            # Use flat data types so that the template can be as simple as possible
            error=escape(error),
            error_description=escape(error_description or ""),
            reset_password_url=self._get_reset_password_url(request),
            ))

    def auth_response(self, request):
        """The auth_response view"""
        result = self._build_auth(request).complete_log_in(request.GET)
        if "error" in result:
            return self._render_auth_error(
                request,
                error=result["error"],
                error_description=result.get("error_description"),
                )
        return redirect("index")  # TODO: Go back to a customizable url

    def logout(self, request):
        """The logout view"""
        return redirect(
            self._build_auth(request).log_out(request.build_absolute_uri("/")))

    def get_user(self, request):
        return self._build_auth(request).get_user()

    def get_token_for_user(self, request, scopes: List[str]):
        return self._build_auth(request).get_token_for_user(scopes)

    def login_required(
        self,
        function=None,  # TODO: /, *, redirect_field_name=None, login_url=None,
    ):
        # With or without parameter. Inspired by https://stackoverflow.com/a/39335652

        # With parameter
        if function is None:
            return partial(
                self.login_required,
                #redirect_field_name=redirect_field_name,
                #login_url=login_url,
            )

        # Without parameter
        @wraps(function)
        def wrapper(request, *args, **kwargs):
            auth = self._build_auth(request)
            if not auth.get_user():
                return redirect(self.login)
            return function(request, *args, **kwargs)
        return wrapper

