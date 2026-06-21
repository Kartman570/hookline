import argparse
import json
from .config import from_env
from .store import Store


def main():
    parser = argparse.ArgumentParser(description='Inspect a local delivery database')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('stats')
    events = commands.add_parser('events')
    events.add_argument('--state', choices=['pending', 'processing', 'delivered', 'dead'])
    events.add_argument('--limit', type=int, default=50)
    replay = commands.add_parser('replay')
    replay.add_argument('id')
    args = parser.parse_args()
    store = Store(from_env().database)
    try:
        if args.command == 'stats':
            result = store.stats()
        elif args.command == 'events':
            result = store.events(args.state, args.limit)
        else:
            store.replay(args.id)
            result = {'id': args.id, 'state': 'pending'}
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
