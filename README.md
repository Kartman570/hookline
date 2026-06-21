# Hookline

A durable webhook queue with an authenticated FastAPI service and separate
workers. It supports idempotent enqueueing, signed requests, retry backoff,
lease recovery, dead-letter replay and an inspectable attempt history.

## Run locally

Python 3.11 is recommended.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
export HOOKLINE_API_KEY="$(python -c 'import secrets; print(secrets.token_hex(24))')"
export HOOKLINE_DATABASE=hookline.sqlite3
uvicorn hookline.api:create_app --factory --host 127.0.0.1 --port 8000
```

In another terminal, use the same environment and start `python -m hookline.worker`.
`--once` processes at most one due event. Both processes must use the same database.
Open `/docs` for the request schemas. `/health` is public; all other application
routes require `Authorization: Bearer <HOOKLINE_API_KEY>`.

For a complete local example, start a receiver in a third terminal:

```sh
export RECEIVER_SECRET="$(python -c 'import secrets; print(secrets.token_hex(24))')"
python -m examples.receiver --port 8090
```

Use that receiver secret and the service token in a shell with both variables:

```sh
curl -s http://127.0.0.1:8000/endpoints \
  -H "Authorization: Bearer $HOOKLINE_API_KEY" -H 'Content-Type: application/json' \
  -d "{\"name\":\"local receiver\",\"url\":\"http://127.0.0.1:8090/hook\",\"secret\":\"$RECEIVER_SECRET\"}"
curl -s http://127.0.0.1:8000/events \
  -H "Authorization: Bearer $HOOKLINE_API_KEY" -H 'Content-Type: application/json' \
  -d '{"endpoint_id":1,"key":"example-one","payload":{"message":"hello"}}'
python -m hookline.admin stats
python -m hookline.admin events --state dead
```

Use the endpoint ID returned by the first request if the database already has
endpoints. Repeating the enqueue request returns the same event. Change the
idempotency key for a new delivery. Inspect `GET /events/{id}/attempts`, replay
with `POST /events/{id}/replay`, and pause a destination with
`PATCH /endpoints/{id}?enabled=false`.

## Containers

Set `HOOKLINE_API_KEY` then run `docker compose up --build`. API and worker share
a named SQLite volume. Configure `HOOKLINE_ALLOWED_HOSTS` as a comma-separated
list of destination hosts. Inside a container, `localhost` is that container;
use a receiver service name or an explicitly allowed host gateway for external
receivers. The API port binds to loopback by default.

## Checks

```sh
python -m unittest discover -s tests -v
ruff check .
coverage run -m unittest discover -s tests
coverage report
```

Tests use temporary SQLite databases and local HTTP receivers. They exercise
real retries, signatures, competing claims, idempotency and API authorization.
See [delivery behavior](docs/delivery.md) for failure semantics and limits.
