from dataclasses import dataclass
import os
from urllib.parse import urlsplit


@dataclass
class Settings:
    database: str
    api_key: str
    allowed_hosts: tuple = ('localhost', '127.0.0.1')
    timeout: float = 5.0
    lease_seconds: float = 30.0

    def __post_init__(self):
        if len(self.api_key) < 16:
            raise ValueError('HOOKLINE_API_KEY must contain at least 16 characters')
        if self.timeout <= 0 or self.lease_seconds <= self.timeout:
            raise ValueError('Lease must be longer than a positive request timeout')

    def validate_url(self, url):
        parsed = urlsplit(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            raise ValueError('An HTTP or HTTPS URL is required')
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError('URL credentials and fragments are not supported')
        if parsed.hostname.lower() not in self.allowed_hosts:
            raise ValueError('Destination host is not allowed')
        try:
            parsed.port
        except ValueError as error:
            raise ValueError('Invalid destination port') from error
        return url


def from_env():
    return Settings(database=os.getenv('HOOKLINE_DATABASE', 'hookline.sqlite3'),
                    api_key=os.getenv('HOOKLINE_API_KEY', ''),
                    allowed_hosts=tuple(host.strip().lower() for host in
                        os.getenv('HOOKLINE_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')))
