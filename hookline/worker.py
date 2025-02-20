import argparse
import random
import time
from .config import from_env
from .store import Store
from .transport import deliver


def backoff(attempt):
    ceiling = min(3600, 2 ** min(attempt, 12))
    return random.uniform(ceiling / 2, ceiling)


def tick(store, settings, now=None):
    now = time.time() if now is None else now
    event = store.claim(now, settings.lease_seconds)
    if event is None:
        return False
    endpoint = store.endpoint(event['endpoint_id'])
    try:
        code, error = deliver(endpoint, event, settings)
    except ValueError:
        code, error = 400, 'InvalidDestination'
    store.finish(event['id'], event['lease_token'], code, error,
                 time.time() if now is None else now, backoff(event['attempts']))
    return True


def main():
    parser = argparse.ArgumentParser(description='Run the webhook delivery worker')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    settings = from_env()
    store = Store(settings.database)
    try:
        while True:
            worked = tick(store, settings)
            if args.once:
                return
            if not worked:
                time.sleep(0.5)
    except KeyboardInterrupt:
        return


if __name__ == '__main__':
    main()
