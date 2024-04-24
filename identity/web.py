from abc import ABC, abstractmethod
import functools
import json
import logging
import time
from typing import (
    List, Dict, Callable,  # Needed in Python 3.7 & 3.8
    Union,  # Needed until Python 3.10+
)

import jwt  # PyJWT
import requests
import msal


logger = logging.getLogger(__name__)


def _get_http_client():  # Better reuse the result of this function to save resources
    http_client = requests.Session()
    a = requests.adapters.HTTPAdapter(
        # Web app/API shall use minimal retry;
        # let the calling client decide their own retry strategy
        max_retries=1)
    http_client.mount("http://", a)
    http_client.mount("https://", a)
    return http_client

@functools.lru_cache(maxsize=128)
def __http_get_json(http_client, url, timestamp):
    return http_client.get(url).json()

def _http_get_json(url, *, http_client):  # Get JSON from a URL or a one-day cache
    return __http_get_json(http_client, url, time.strftime("%x"))


class Auth(object):  # This a low level helper which is web framework agnostic
    # These key names are hopefully unique in session
    _TOKEN_CACHE = "_token_cache"
    _AUTH_FLOW = "_auth_flow"
    _USER = "_logged_in_user"
    _EXPLICITLY_REQUESTED_SCOPES = f"{__name__}.explicitly_requested_scopes"
    _STATE_NO_OP = f"{__name__}.no_op"  # A special state to indicate an auth response shall be ignored
    __NEXT_LINK = f"{__name__}.next_link"  # The next page after a successful auth
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
        self._http_client = _get_http_client()

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
        self, scopes=None, redirect_uri=None, state=None, prompt=None,
        next_link=None,
    ):
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
            flow = app.initiate_device_flow(_scopes)
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

    def complete_log_in(self, auth_response=None):
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

    def log_out(self, homepage):
        # The vocabulary is "log out" (rather than "sign out") in the specs
        # https://openid.net/specs/openid-connect-frontchannel-1_0.html
        """Logs out the user from current app.

        :param str homepage:
            The page to be redirected to, after the log-out.
            In Flask, you can pass in ``url_for("index", _external=True)``.

        :return:
            An upstream log-out URL. You can optionally guide user to visit it,
            otherwise the user remains logged-in there, and can SSO back to your app.
        """
        self._session.pop(self._USER, None)  # Must
        self._session.pop(self._TOKEN_CACHE, None)  # Optional
        try:
            # The self._authority ends up w/ the V1 endpoint of Microsoft Entra ID,
            # which is still good enough for log_out()
            a = self._oidc_authority or self._authority
            e = _http_get_json(
                # Empirically, Microsoft Entra ID /v2 endpoint shows an account picker
                # but its default (i.e. v1) endpoint will sign out the (only?) account
                f"{a}/.well-known/openid-configuration",
                http_client=self._http_client).get("end_session_endpoint")
        except requests.exceptions.RequestException as e:
            logger.exception("Failed to get OIDC config")
            return homepage
        else:
            return f"{e}?post_logout_redirect_uri={homepage}" if e else homepage

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
        oidc_authority: str=None,
        authority: str=None,
        redirect_uri: str=None,
        # We end up accepting Microsoft Entra ID B2C parameters rather than generic urls
        # because it is troublesome to build those urls in settings.py or templates
        b2c_tenant_name: str=None,
        b2c_signup_signin_user_flow: str=None,
        b2c_edit_profile_user_flow: str=None,
        b2c_reset_password_user_flow: str=None,
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
        self._http_cache = {}  # All subsequent Auth instances will share this

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

    def _build_auth(self, session):
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
    def _render_auth_error(error, *, error_description=None):
        # The default auth_error.html template may or may not escape.
        # If a web framework does not escape it by default, a subclass shall escape it.
        pass


class HttpError(Exception):
    def __init__(self, status_code, *, headers, description=None):
        self.status_code = status_code
        self.headers = headers
        self.description = description


class ApiAuth(ABC):  # Unlike Auth, this does not use session
    _INVALID_REQUEST = "invalid_request"
    _INVALID_TOKEN = "invalid_token"
    _INSUFFICIENT_SCOPE = "insufficient_scope"

    def __init__(
        self,
        *,
        client_id,
        oidc_authority=None,
        authority=None,
        client_credential=None,
    ):
        """Create an ApiAuth instance for a web API.

        This instance is expected to be long-lived with the web app.

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
        self._client_id = client_id
        self._client_credential = client_credential
        self._oidc_authority = oidc_authority
        self._authority = authority
        self._realm = oidc_authority or authority
        self._http_client = _get_http_client()

    def raise_http_error(self, status_code, *, headers=None, description=None):
        # This can be overridden by a subclass for each web framework.
        # If a web framework (Django) does not have a way to raise an HTTP error,
        # its subclass or app must catch HttpError and render a response accordingly.
        raise HttpError(status_code, headers=headers, description=description)

    def __raise_oauth2_error(
        self,
        error_code:str,
        *,
        error_description:str = None,
        error_uri:str = None,
        scopes:List[str] = None,
    ):
        # https://datatracker.ietf.org/doc/html/rfc6750#section-3
        auth_params = ", ".join(
            '{k}: "{v}"'.format(k=k, v=v.replace('"', "'")) for k, v in dict(
                realm=self._realm,
                error=error_code,
                error_description=error_description,
                error_uri=error_uri,
                scope=' '.join(scopes) if scopes else None,
            ).items() if v and isinstance(v, str))
        self.raise_http_error(
            {  # https://datatracker.ietf.org/doc/html/rfc6750#section-3.1
                self._INVALID_REQUEST: 400,
                self._INVALID_TOKEN: 401,
                self._INSUFFICIENT_SCOPE: 403,
            }.get(error_code, 400),
            headers={"WWW-Authenticate": f'Bearer {auth_params}'},
            description=f"{error_code}: {error_description}",
            )

    def _oidc_discovery(self):
        idp = self._oidc_authority or f"{self._authority}/v2.0"  # Matching MSAL behavior
        oidc_discovery = f"{idp}/.well-known/openid-configuration"
        logger.debug("OIDC Discovery from %s (probably via cache)", oidc_discovery)
        return _http_get_json(oidc_discovery, http_client=self._http_client)

    @functools.lru_cache(maxsize=128)
    def __get_keys(self, timestamp):
        # Returns the keys from the authority's jwks_uri, remap to {kid: PyJWT's key}
        if not (self._oidc_authority or self._authority):
            self.raise_http_error(  # So the API errors out gracefully
                500, description="No authority to fetch keys from")
        idp = self._oidc_authority or f"{self._authority}/v2.0"  # Matching MSAL behavior
        try:
            conf = self._oidc_discovery()
            try:
                return {
                    jwk["kid"]: dict(  # Empirically, kid always exists in the wild
                        jwk,  # https://www.rfc-editor.org/rfc/rfc7517.html#section-4.5
                        # Inspired from https://stackoverflow.com/a/68891371/728675
                        pyjwt_key=jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk)),
                    ) for jwk in _http_get_json(
                        conf["jwks_uri"], http_client=self._http_client)["keys"]
                }
            except KeyError as e:
                self.raise_http_error(500, description=f'Key should have "kid": {e}')
        except requests.exceptions.RequestException as e:
            self.raise_http_error(500, description=f"Failed to get keys: {e}")

    def _get_keys(self):
        return self.__get_keys(time.strftime("%x"))  # Refresh keys daily

    def _validate_bearer_token(
        self,
        token:str, *,
        scopes:Union[List[str], Dict[str, str]],
    ):
        # Return claims of the JWT if valid, otherwise calls __raise_oauth2_error()
        try:
            kid = jwt.get_unverified_header(token)["kid"]
            key = self._get_keys().get(kid)
            if not key:
                self.__raise_oauth2_error(
                    self._INVALID_TOKEN,
                    error_description=f"Key not found for kid {kid}")
            claims = jwt.decode(
                token,
                key["pyjwt_key"],
                algorithms=["RS256"],  # Hardcode it to prevent downgrade attack
                audience=self._client_id,
                )  # https://pyjwt.readthedocs.io/en/stable/api.html#jwt.decode

            expected_scopes = set(scopes or [])
            authorized_scopes = set(claims.get("scp", "").split())
            if expected_scopes - authorized_scopes:
                # TODO: It could also be daemon app. Need to support actor validation
                # https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation#validate-the-actor
                self.__raise_oauth2_error(
                    self._INSUFFICIENT_SCOPE,
                    error_description="Insufficient scope(s). "
                        f'''This API expects "{' '.join(expected_scopes)}", '''
                        f'''but got only "{' '.join(authorized_scopes)}".''',
                    # scopes can be a dict of {"scope_in_scp": "scope in request"}
                    scopes=scopes.values() if isinstance(scopes, dict) else scopes)

            # https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens#recap
            expected_issuer = key.get("issuer") or self._oidc_discovery()["issuer"]
            if self._authority and "tid" in claims:  # Microsoft Entra ID code path
                expected_issuer = expected_issuer.replace("{tenantid}", claims["tid"])
            if claims.get("iss") != expected_issuer:
                self.__raise_oauth2_error(
                    self._INVALID_TOKEN, error_description="Issuer mismatch. "
                        f"(Expected {expected_issuer}, got {claims.get('iss')})")
            return claims

        except (
            jwt.DecodeError, jwt.InvalidSignatureError, jwt.InvalidAudienceError,
        ) as e:
            self.__raise_oauth2_error(self._INVALID_TOKEN, error_description=f"{e}")

    def _validate(
        self,
        request,  # We expect request.headers to be a dict-like object
        *,
        expected_scopes,  # Defined in _validate_bearer_token(),
            # documented in authorization_required()
    ):
        authz = request.headers.get("Authorization")
        # https://datatracker.ietf.org/doc/html/rfc6750#section-3
        if not authz:
            self.raise_http_error(
                401,  # https://stackoverflow.com/a/6937030/728675
                headers={"WWW-Authenticate": f'Bearer realm="{self._realm}"'},
                description="Authorization header is missing",
            )
        authz_parts = authz.split(maxsplit=1)
        scheme = authz_parts[0]
        params = authz_parts[1:]  # May be an empty list
        if scheme == "Bearer" and params:
            context = {
                "claims":  # TODO: Decide on the name
                    self._validate_bearer_token(
                        params[0], scopes=expected_scopes),
                }
        # TODO: Support more schemes
        else:
            self.raise_http_error(
                401,
                headers={"WWW-Authenticate": f'Bearer realm="{self._realm}"'},
                description=f"Authorization header is invalid. ({authz})",
            )
        return context

    @abstractmethod
    def authorization_required(  # Lengthy but precise name
        self,
        *,
        expected_scopes:List[str],  # TODO: Accept a callable in RESTful API scenario?
        #extra_scopes: List[str]=None,  # TODO: For OBO
    ):
        # Sub-classes inherit the docstring, so we only document the commen params.
        """It returns a decorator that verifies the request's authorization header.

        A request not meeting the requirement(s) will raise an HTTP 401 Unauthorized.
        For a valid request, the view will be called with a keyword argument
        named "context" which is a dict containing the user object.

        Usage::

            @settings.AUTH.authorization_required(expected_scopes=["foo", "bar"])
            def resource(..., *, context):  # The ... part is differnt per web framework
                # The user is uniquely identified by claims['sub'] or claims["oid"],
                # claims['tid'] and/or claims['iss'].
                claims = context["claims"]
                return {"content": f"content for {claims['sub']}@{claims['tid']}"}

        :param expected_scopes:
            These scopes are expected to be present in the token's "scp" claim.
            If not, the view will emit an HTTP 401 Unauthorized or HTTP 403 Forbidden.
        """
        raise NotImplementedError("Subclass must implement this method")

