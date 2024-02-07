from requests import Session, adapters
from urllib3.util.retry import Retry

class RequestsHelper:

    _discovery_key_session = None

    def __init__(self):
        raise RuntimeError('Call get_discovery_key_session instead')

    @staticmethod
    def get_discovery_key_session():
        if RequestsHelper._discovery_key_session is None:
            session = Session()
            retries = Retry(total=5,
                backoff_factor=0.1,
                status_forcelist=[ 500, 502, 503, 504 ])
            session.mount('https://', adapters.HTTPAdapter(max_retries=retries))
            session.mount('http://', adapters.HTTPAdapter(max_retries=retries))
            RequestsHelper._discovery_key_session = session

        return RequestsHelper._discovery_key_session
