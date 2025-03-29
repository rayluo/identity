from abc import ABC, abstractmethod
import functools
import logging
import time
from typing import List, Optional  # Needed in Python 3.7 & 3.8

import requests
import msal


logger = logging.getLogger(__name__)


class Auth(object):  # This a low level helper which is web framework agnostic
    # These key names are hopefully unique in session
    _TOKEN_CACHE = "_token_cache"
    _AUTH_FLOW = "_auth_flow"
    _USER = "_logged_in_user"
    _EXPLICITLY_REQUESTED_SCOPES = f"{__name__}.explicitly_requested_scopes"
    _STATE_NO_OP = f"{__name__}.no_op"  # A special state to indicate an auth response shall be ignored
    __NEXT_LINK = f"{__name__}.next_link"  # The next page after a successful auth
    _END_SESSION_ENDPOINT = "end_session_endpoint"

    def __init__(
            self,
            *,
            session,
            client_id,
            oidc_authority=None,
            authority=None,
            client_credential=None,
            http_cache=None,
            ):
        """Create an identity helper for a web app.

        This instance is expected to be long-lived with the web app.

        :param dict session:
            A dict-like object to hold the session data.
            If you are using Flask, you should pass in ``session``.
            If you are using Django, you should pass in ``request.session``.

        :param str oidc_authority:
            The authority which your app registers with your OpenID Connect provider.
            For example, ``https://example.com/foo``.
            This library will concatenate ``/.well-known/openid-configuration``
            to form the metadata endpoint.

        :param str authority:
            The authority which your app registers with your Microsoft Entra ID.
            For example, ``https://example.com/foo``.
            Historically, the underlying library will *sometimes* automatically
            append "/v2.0" to it.
            If you do not want that behavior, you may use ``oidc_authority`` instead.

        :param str client_id:
            The client_id of your web app, issued by its authority.

        :param str client_credential:
            It is somtimes a string.
            The actual format is decided by the underlying auth library. TBD.
        """
        self._session = session
        self._oidc_authority = oidc_authority
        self._authority = authority
        self._client_id = client_id
        self._client_credential = client_credential
        self._http_cache = {} if http_cache is None else http_cache   # All subsequent MSAL instances will share this

    def _load_cache(self):
        cache = msal.SerializableTokenCache()
        if self._session.get(self._TOKEN_CACHE):
            cache.deserialize(self._session[self._TOKEN_CACHE])
        return cache

    def _save_cache(self, cache):
        if cache.has_state_changed:
            self._session[self._TOKEN_CACHE] = cache.serialize()

    def _build_msal_app(self, client_credential=None, cache=None):
        # Web app uses one token cache per user, so we create new MSAL app per token cache
        return (msal.ConfidentialClientApplication
                if client_credential else msal.PublicClientApplication)(
            self._client_id,
            client_credential=client_credential,
            oidc_authority=self._oidc_authority,
            authority=self._authority,
            token_cache=cache,
            http_cache=self._http_cache,  # Share same http_cache among MSAL instances
            instance_discovery=False,  # So that we stick with standard OIDC behavior
            )

    def _load_user_from_session(self):
        return self._session.get(self._USER)  # It may already be expired

    def _save_user_into_session(self, id_token_claims):
        self._session[self._USER] = id_token_claims

    def log_in(
        self,
        *,
        scopes: Optional[List[str]] = None,
        redirect_uri: Optional[str] = None,
        state: Optional[str] = None,
        prompt: Optional[str] = None,
        next_link: Optional[str] = None,
    ) -> dict:
        """This is the first leg of the authentication/authorization.

        :param list scopes:
            A list of scopes that your app will need to use.

        :param str redirect_uri:
            Optional.
            If present, it must be an absolute uri you registered for your web app.
            In Flask, if your redirect_uri function is named ``def auth_response()``,
            then you can use ``url_for("auth_response", _external=True)``.

            If absent, your end users will log in to your web app
            using a different method named Device Code Flow.
            It is less convenient for end user, but still works.

        :param str state:
            Optional. Useful when the caller wants keep their own state.

        :param str prompt:
            Optional. Valid values are defined in
            `OIDC <https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest>`_

        :param str next_link: The link, typically a path, to redirect to after login.

        Returns a dict containing the ``auth_uri`` that you need to guide end user to visit.
        If your app has no redirect uri, this method will also return a ``user_code``
        which you shall also display to end user for them to use during log-in.
        """
        if not self._client_id:
            raise ValueError("client_id must be provided")
        _scopes = scopes or []
        app = self._build_msal_app()  # Only need a PCA at this moment
        if redirect_uri:
            flow = app.initiate_auth_code_flow(
                _scopes, redirect_uri=redirect_uri, state=state, prompt=prompt)
        else:
            if state:
                logger.warning("state only works in redirect_uri mode")
            try:
                flow = app.initiate_device_flow(_scopes)
            except ValueError:  # Either Device Code endpoint unavailable or JsonDecodeError
                return {
                    "error": "configuration_error",
                    "error_description":
                        "This authority does not support device code flow. "
                        "Please configure a redirect_uri to use auth code flow.",
                    }
        if "error" in flow:
            return flow
        flow[self._EXPLICITLY_REQUESTED_SCOPES] = _scopes  # Can be different than the flow["scope"] which is possibly injected by OIDC library
        flow[self.__NEXT_LINK] = next_link
        self._session[self._AUTH_FLOW] = flow
        if redirect_uri:
            return {
                "auth_uri": self._session[self._AUTH_FLOW]["auth_uri"],
                }
        else:
            return {
                "auth_uri": flow["verification_uri"],
                "user_code": flow["user_code"],
                }

    def complete_log_in(self, auth_response: Optional[dict] = None) -> dict:
        """This is the second leg of the authentication/authorization.

        It is used inside your redirect_uri controller.

        :param dict auth_response:
            A dict-like object containing the parameters issued by Identity Provider.
            If you are using Flask, you can pass in ``request.args``.
            If you are using Django, you can pass in ``HttpRequest.GET``.

            If you were using Device Code Flow, you won't have an auth response,
            in that case you can leave it with its default value ``None``.
        :return:
            * On failure, a dict containing "error" and optional "error_description",
              for you to somehow render it to end user.
            * On success, a dict as {"next_link": "/path/to/next/page/if/any"}
              That dict is actually the claims from an already-validated ID token.
        """
        if auth_response and auth_response.get("state") == self._STATE_NO_OP:
            return {}  # Return a no-op, as that is what the request opted for
        auth_flow = self._session.get(self._AUTH_FLOW, {})
        if not auth_flow:
            logger.warning(
                "We found no prior log_in() info from current session. "
                "This situation may be caused by: "
                "(1) sessions were all reset due to a recent server restart, "
                "in which case you can simply start afresh with a new log-in, or "
                "(2) the session was stored on the file system of another server, "
                "in which case you must use either a centralized session store "
                "or a load balancer with sticky session (a.k.a. affinity cookie)."
            )
            return {}  # Return a no-op for this non-actionable error
        cache = self._load_cache()
        if auth_response:  # Auth Code flow
            try:
                result = self._build_msal_app(
                    client_credential=self._client_credential,
                    cache=cache,
                    ).acquire_token_by_auth_code_flow(auth_flow, auth_response)
            except ValueError as e:  # Usually caused by CSRF
                logger.exception("Encountered %s", e)
                return {}  # Return a no-op for this non-actionable error
        else:  # Device Code flow
            result = self._build_msal_app(cache=cache).acquire_token_by_device_flow(
                auth_flow,
                exit_condition=lambda flow: True,
                )
        if "error" in result:
            return result
        if "scope" in result:
            # Only partial scopes were granted, others were likely unsupported.
            # according to https://datatracker.ietf.org/doc/html/rfc6749#section-5.1
            ungranted_scopes = set(
                auth_flow[self._EXPLICITLY_REQUESTED_SCOPES]
                ) - set(result["scope"].split())
            if ungranted_scopes:
                return {
                    "error": "invalid_scope",  # https://datatracker.ietf.org/doc/html/rfc6749#section-5.2
                    "error_description": "Ungranted scope(s): {}".format(
                        ' '.join(ungranted_scopes)),
                }
        # TODO: Reject a re-log-in with a different account?
        self._save_user_into_session(result["id_token_claims"])
        self._save_cache(cache)
        flow = self._session.pop(self._AUTH_FLOW, {})
        return {"next_link": flow.get(self.__NEXT_LINK)}

    def get_user(self):
        """Returns None if the user has not logged in or no longer passes validation.
        Otherwise returns a dict representing the current logged-in user.

        The dict will have following keys:

        * ``sub``. It is the unique identifier of the current logged-in user.
          You can use it to create an entry in your web app's local database.
        * Some of `other claims <https://openid.net/specs/openid-connect-core-1_0.html#StandardClaims>`_
        """
        id_token_claims = self._load_user_from_session()
        if not id_token_claims:  # No user has logged in
            return None
        if _is_valid(id_token_claims):  # Did not expire
            return id_token_claims
        result = self._get_token_for_user([], force_refresh=True)  # Update ID token
        if "error" not in result:
            return self._load_user_from_session()

    def get_token_for_user(self, scopes):
        """Get access token silently for the current user, with specified scopes.

        :param list scopes:
            A list of scopes that your app will need to use.

        :return: A dict representing the json response from identity provider.

            - A successful response would contain "access_token" key,
            - An error response would contain "error" and usually "error_description".

            See also `OAuth2 specs <https://www.rfc-editor.org/rfc/rfc6749#section-5>`_.
        """
        return self._get_token_for_user(scopes)

    def _get_token_for_user(self, scopes, force_refresh=None):
        error_response = {"error": "interaction_required", "error_description": "User need to log in and/or consent"}
        user = self._load_user_from_session()
        if not user:
            return {"error": "interaction_required", "error_description": "Log in required"}
        cache = self._load_cache()  # This web app maintains one cache per session
        app = self._build_msal_app(
            client_credential=self._client_credential, cache=cache)
        accounts = app.get_accounts(username=user.get("preferred_username"))
        if accounts:
            result = app.acquire_token_silent_with_error(
                scopes, account=accounts[0], force_refresh=force_refresh)
            self._save_cache(cache)  # Cache might be refreshed. Save it.
            if result and result.get("id_token_claims"):
                self._save_user_into_session(result["id_token_claims"])
            if result:
                return result
        return {"error": "interaction_required", "error_description": "Cache missed"}

    @functools.lru_cache(maxsize=1)
    def _get_oidc_config(self):
        # The self._authority is usually the V1 endpoint of Microsoft Entra ID,
        # which is still good enough for log_out()
        a = self._oidc_authority or self._authority
        conf = requests.get(f"{a}/.well-known/openid-configuration").json()
        if not conf.get(self._END_SESSION_ENDPOINT):
            logger.warning(
                "%s not found from OIDC config: %s", self._END_SESSION_ENDPOINT, conf)
        return conf

    def log_out(self, post_logout_redirect_uri: str) -> str:
        # The vocabulary is "log out" (rather than "sign out") in the specs
        # https://openid.net/specs/openid-connect-frontchannel-1_0.html
        """Logs out the user from current app.

        :param str post_logout_redirect_uri:
            The absolute uri of the page to be redirected to, after the log-out.
            In Flask, you can pass in ``url_for("index", _external=True)``.

        :return:
            An upstream log-out URL. You can optionally guide user to visit it,
            otherwise the user remains logged-in there, and can SSO back to your app.
        """
        self._session.pop(self._USER, None)  # Must
        self._session.pop(self._TOKEN_CACHE, None)  # Optional
        try:
            # Empirically, Microsoft Entra ID's /v2.0 endpoint shows an account picker
            # but its default (i.e. v1.0) endpoint will sign out the (only?) account
            endpoint = self._get_oidc_config().get(self._END_SESSION_ENDPOINT)
            if endpoint:
                return f"{endpoint}?post_logout_redirect_uri={post_logout_redirect_uri}"
        except requests.exceptions.RequestException:
            logger.exception("Failed to get OIDC config")
        logger.warning("No end_session_endpoint found. Fallback to %s", post_logout_redirect_uri)
        return post_logout_redirect_uri  # Fall back to this

    def get_token_for_client(self, scopes):
        """Get access token for the current app, with specified scopes.

        :param list scopes:
            A list of scopes that your app will need to use.

        :return: A dict representing the json response from identity provider.

            - A successful response would contain "access_token" key,
            - An error response would contain "error" and usually "error_description".

            See also `OAuth2 specs <https://www.rfc-editor.org/rfc/rfc6749#section-5>`_.
        """
        # TODO: Where shall token cache come from?
        app = self._build_msal_app(client_credential=self._client_credential)
        result = app.acquire_token_silent(scopes, account=None)
        return result if (
            result and "access_token" in result
            ) else app.acquire_token_for_client(scopes)


def _is_valid(id_token_claims, skew=None, seconds=None):
    skew = 210 if skew is None else skew
    now = time.time()
    logger.debug("now=%s, iat=%s, skew=%s", now, id_token_claims["iat"], skew)
    return now < skew + (
        id_token_claims["exp"] if seconds is None
        else id_token_claims["iat"] + seconds)


class WebFrameworkAuth(ABC):  # This is a mid-level helper to be subclassed
    """This is a mid-level helper to be subclassed. Do not use it directly."""
    def __init__(
        self,
        client_id: str,
        *,
        client_credential=None,
        oidc_authority: Optional[str] = None,
        authority: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        # We end up accepting Microsoft Entra ID B2C parameters rather than generic urls
        # because it is troublesome to build those urls in settings.py or templates
        b2c_tenant_name: Optional[str] = None,
        b2c_signup_signin_user_flow: Optional[str] = None,
        b2c_edit_profile_user_flow: Optional[str] = None,
        b2c_reset_password_user_flow: Optional[str] = None,
    ):
        """Create an identity helper for a web application.

        :param str client_id:
            The client_id of your web application, issued by its authority.

        :param str client_credential:
            It is somtimes a string.
            The actual format is decided by the underlying auth library. TBD.

        :param str oidc_authority:
            The authority which your app registers with your OpenID Connect provider.
            For example, ``https://example.com/foo``.
            This library will concatenate ``/.well-known/openid-configuration``
            to form the metadata endpoint.

        :param str authority:
            The authority which your app registers with your Microsoft Entra ID.
            For example, ``https://example.com/foo``.
            Historically, the underlying library will *sometimes* automatically
            append "/v2.0" to it.
            If you do not want that behavior, you may use ``oidc_authority`` instead.

        :param str redirect_uri:
            This will be used to mount your project's auth views accordingly.

            For example, if your input here is ``https://example.com/x/y/z/redirect``,
            then your project's redirect page will be mounted at "/x/y/z/redirect",
            login page will be at "/x/y/z/login",
            and logout page will be at "/x/y/z/logout".

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
        self._redirect_uri = redirect_uri
        self._http_cache: dict = {}  # All subsequent Auth instances will share this

        self._authority: Optional[str] = None  # It makes mypy happy
        # Note: We do not use overload, because we want to allow the caller to
        # have only one code path that relay in all the optional parameters.
        if b2c_tenant_name and b2c_signup_signin_user_flow:
            b2c_authority_template = (  # TODO: Support custom domain
                "https://{tenant}.b2clogin.com/{tenant}.onmicrosoft.com/{user_flow}")
            self._authority = b2c_authority_template.format(
                tenant=b2c_tenant_name,
                user_flow=b2c_signup_signin_user_flow,
                http_cache=self._http_cache,
                )
            self._edit_profile_auth = Auth(
                session={},
                authority=b2c_authority_template.format(
                    tenant=b2c_tenant_name,
                    user_flow=b2c_edit_profile_user_flow,
                    ),
                client_id=client_id,
                http_cache=self._http_cache,
                ) if b2c_edit_profile_user_flow else None
            self._reset_password_auth = Auth(
                session={},
                authority=b2c_authority_template.format(
                    tenant=b2c_tenant_name,
                    user_flow=b2c_reset_password_user_flow,
                    ),
                client_id=client_id,
                http_cache=self._http_cache,
                ) if b2c_reset_password_user_flow else None
        else:
            self._authority = authority
            self._edit_profile_auth = None
            self._reset_password_auth = None
        self._oidc_authority = oidc_authority

    def _get_configuration_error(self):
        # Do not raise exception, because
        # we want to render a nice error page later during login,
        # which is a better developer experience especially for deployment
        if not (self._client_id and (self._oidc_authority or self._authority)):
            return """Almost there. Did you forget to setup at least these settings?
(1) CLIENT_ID, and either
(2.1) OIDC_AUTHORITY, or
(2.2) AUTHORITY, or
(2.3) the B2C_TENANT_NAME and SIGNUPSIGNIN_USER_FLOW pair?
"""

    def _build_auth(self, session) -> Auth:
        return Auth(
            session=session,
            oidc_authority=self._oidc_authority,
            authority=self._authority,
            client_id=self._client_id,
            client_credential=self._client_credential,
            http_cache=self._http_cache,
            )

    def _login_required(self, auth: Auth, user: dict, scopes: List[str]):
        # Returns the context. This logic is reused in the login_required decorators.
        context = None
        if user:
            if scopes:
                result = auth.get_token_for_user(scopes)  # Silently via RT
                if isinstance(result, dict) and "access_token" in result:
                    context = dict(
                        user=user,
                        # https://datatracker.ietf.org/doc/html/rfc6749#section-5.1
                        access_token=result["access_token"],
                        token_type=result.get("token_type", "Bearer"),
                        expires_in=result.get("expires_in", 300),
                        refresh_token=result.get("refresh_token"),
                    )
                    context["scopes"] = result["scope"].split() if result.get(
                        "scope") else scopes
                else:  # Token request failed
                    logger.error(
                        "Access token unavailable. Error: %s, Desc: %s, keys: %s",
                        result.get("error"), result.get("error_description"),
                        result.keys())
                    context = None  # Token request failed
            else:
                context = {"user": user}
        else:  # User has not logged in at all
            context = None
        return context

    def get_edit_profile_url(self):
        """A helper to get the URL for Microsoft Entra B2C's edit profile page.

        You can pass this URL to your template and render it there.
        """
        return self._edit_profile_auth.log_in(
            redirect_uri=self._redirect_uri,
            state=self._edit_profile_auth._STATE_NO_OP,
            )["auth_uri"] if self._edit_profile_auth and self._redirect_uri else None

    def _get_reset_password_url(self):
        return self._reset_password_auth.log_in(
            redirect_uri=self._redirect_uri,
            state=self._reset_password_auth._STATE_NO_OP,
            )["auth_uri"] if self._reset_password_auth and self._redirect_uri else None

    @abstractmethod
    def _render_auth_error(
        error, *, error_description=None,
    ):  # Return value could be a str, or a framework-specific Response object
        # The default auth_error.html template may or may not escape.
        # If a web framework does not escape it by default, a subclass shall escape it.
        pass
