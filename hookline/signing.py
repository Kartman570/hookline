import hashlib
import hmac


def signature(secret, stamp, body):
    value = str(stamp).encode() + b'.' + body
    return hmac.new(secret.encode(), value, hashlib.sha256).hexdigest()


def verify(secret, stamp, body, supplied, now, tolerance=300):
    try:
        if abs(now - int(stamp)) > tolerance:
            return False
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(signature(secret, stamp, body).encode(), supplied.encode())
