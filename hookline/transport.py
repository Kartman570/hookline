from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import time
from .signing import signature


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, newurl):
        return None


def deliver(endpoint, event, settings):
    settings.validate_url(endpoint['url'])
    body = event['payload'].encode()
    stamp = str(int(time.time()))
    headers = {'Content-Type': 'application/json', 'X-Hookline-Id': event['id'],
               'X-Hookline-Timestamp': stamp,
               'X-Hookline-Signature': signature(endpoint['secret'], stamp, body)}
    request = Request(endpoint['url'], data=body, headers=headers, method='POST')
    opener = build_opener(NoRedirect(), ProxyHandler({}))
    try:
        with opener.open(request, timeout=settings.timeout) as response:
            return response.status, None
    except HTTPError as error:
        status = error.code
        error.close()
        return status, None
    except (URLError, OSError) as error:
        return None, type(error).__name__
