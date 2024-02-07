from jose import jwt

from identity.exceptions import AuthenticationError
from identity.helpers import RequestsHelper

class Auth:

    def __init__(self):
        pass

    def get_token(self, request, keyword="bearer"):
        # Retrieve token from authorization header.
        # Microsoft Entra gives bearer tokens. Keyword by default is bearet but
        # can a dveloper want to have a custome keyword e.g in Django by default its Token

        auth_header = request.headers.get('Authorization')

        if not auth_header:
            raise AuthenticationError(
                {
                    "code": "missing_authentication_header",
                    "details": "Expected authorization header but couldn't find it."
                },
                401
            )

        auth_header_sections = auth_header.split()
        auth_header_length = len(auth_header_sections)

        if auth_header_length <= 1 or auth_header_length > 2:
            raise AuthenticationError(
                {
                    "code": "invalid_header",
                    "details": f"Authorization header is malformed."
                }, 
                401
            )

        if auth_header_sections[0].lower() != keyword.lower():
            raise AuthenticationError(
                {
                    "code": "invalid_header",
                    "details": f"Authorization header must start with {keyword}"
                }, 
                401
            )

        return auth_header_sections[1]


    def is_valid_aud(self, aud, app_id_uris):
        # app_id_uris is an array. This is beause of the possibility of an app registration having multiple
        # appid URIS https://learn.microsoft.com/entra/identity-platform/reference-app-manifest#identifieruris-attribute
        return aud in app_id_uris

    def is_valid_issuer(self, iss, tenant_id, multitenant=False):
        # Validating the issuer may require an exact match or a pattern match
        # For multitenant apps, you'll need a pattern match as the tenant id varies
        # https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens
        # multi tenant apps dont need to have tenant_id. Do we need to make 
        # tenant_id optional?

        if multitenant:
            return iss.startswith("https://login.microsoftonline.com/") and iss.endswith("/v2")
        return iss == f"https://login.microsoftonline.com/{tenant_id}/v2"

    def get_rsa_key(self, authority, token):

        key_url = f"{authority}/discovery/v2.0/keys"
        jwks = RequestsHelper.get_discovery_key_session().get(key_url).json()
        unverified_header = jwt.get_unverified_header(token)

        try:
            rsa_key = {}

            for key in jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"]
                    }        
        except Exception as exc:
            # Is there possibility of an exceotion being raised here?
            # adding a try except incase something breaks
            raise AuthenticationError(
                {
                    "code": "invalid_header",
                    "detailsn":"Unable to generate rsa key"
                }, 
                401
            ) from exc
            
        return rsa_key
        
    def validate_token_signing(self, authority, token):

        rsa_key = self.get_rsa_key(authority, token)

        if rsa_key:

            # we are not checking aud and issuer as those need to be explicitly checked

            try:
                jwt.decode(
                    token,
                    rsa_key,
                    algorithms=["RS256"]
                )
                
                return {"code": "valid_signature","details": "Token singature is valid"}, 
            except jwt.ExpiredSignatureError as jwt_expired_exc:
                raise AuthenticationError(
                    {"code": "token_expired","details": "Token is expired"}, 
                    401
                ) from jwt_expired_exc
            except jwt.JWTClaimsError as jwt_claims_exc:
                # Only claim here now is algorithms?
                raise AuthenticationError(
                    {"code": "invalid_claims","details":"incorrect claims. Wrong algorithm used"},
                    401
                ) from jwt_claims_exc
            except Exception as exc:
                raise AuthenticationError(
                    {"code": "invalid_header","details":"Error parsing token."},
                    401
                ) from exc
            
        raise AuthenticationError(
            {"code": "invalid_header","details": "Invalid RSA key"},
            401
        )
