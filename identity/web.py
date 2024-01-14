import logging
import time

import msal


logger = logging.getLogger(__name__)


class Auth(object):
    # These key names are hopefully unique in session
    _TOKEN_CACHE = "_token_cache"
    _AUTH_FLOW = "_auth_flow"
    _USER = "_logged_in_user"
    def __init__(
            self,
            *,
            session,
            authority,
            client_id,
            client_credential=None,
            ):
        """Create an identity helper for a web app.

        This instance is expected to be long-lived with the web app.

        :param dict session:
            A dict-like object to hold the session data.
            If you are using Flask, you should pass in ``session``.
            If you are using Django, you should pass in ``request.session``.

        :param str authority:
            The authority which your app registers with.
            For example, ``https://example.com/foo``.

        :param str client_id:
            The client_id of your web app, issued by its authority.

        :param str client_credential:
            It is somtimes a string.
            The actual format is decided by the underlying auth library. TBD.
        """
        self._session = session
        self._authority = authority
        self._client_id = client_id
        self._client_credential = client_credential
        self._http_cache = {}  # All subsequent MSAL instances will share this

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
            authority=self._authority,
            token_cache=cache,
            http_cache=self._http_cache,  # Share same http_cache among MSAL instances
            )

    def _load_user_from_session(self):
        return self._session.get(self._USER)  # It may already be expired

    def _save_user_into_session(self, id_token_claims):
        self._session[self._USER] = id_token_claims

    def log_in(self, scopes=None, redirect_uri=None, state=None, prompt=None):
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

        Returns a dict containing the ``auth_uri`` that you need to guide end user to visit.
        If your app has no redirect uri, this method will also return a ``user_code``
        which you shall also display to end user for them to use during log-in.
        """
        _scopes = scopes or []
        app = self._build_msal_app()  # Only need a PCA at this moment
        if redirect_uri:
            flow = app.initiate_auth_code_flow(
                _scopes, redirect_uri=redirect_uri, state=state, prompt=prompt)
            self._session[self._AUTH_FLOW] = flow
            return {
                "auth_uri": self._session[self._AUTH_FLOW]["auth_uri"],
                }
        else:
            if state:
                logger.warning("state only works in redirect_uri mode")
            flow = app.initiate_device_flow(_scopes)
            self._session[self._AUTH_FLOW] = flow
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
            * On success, a dict containing the info of current logged-in user.
              That dict is actually the claims from an already-validated ID token.
        """
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
        # TODO: Reject a re-log-in with a different account?
        self._save_user_into_session(result["id_token_claims"])
        self._save_cache(cache)
        self._session.pop(self._AUTH_FLOW, None)
        return self._load_user_from_session()

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
        """Get access token for the current user, with specified scopes.

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
            if result.get("id_token_claims"):
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
        return "{authority}/oauth2/v2.0/logout?post_logout_redirect_uri={hp}".format(
            authority=self._authority, hp=homepage)

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

