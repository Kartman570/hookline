# API reference

| Method | Path | Result |
| --- | --- | --- |
| GET | `/health` | Storage readiness; 503 when unavailable |
| POST | `/endpoints` | Create a named URL with a signing secret |
| GET | `/endpoints` | List destinations without secrets |
| PATCH | `/endpoints/{id}?enabled=false` | Pause future claims |
| POST | `/events` | Enqueue or return an idempotent duplicate |
| GET | `/events?state=dead&limit=50&offset=0` | Browse a bounded page |
| GET | `/events/{id}` | Inspect payload and delivery state |
| GET | `/events/{id}/attempts` | List completed and current attempts |
| POST | `/events/{id}/replay` | Give a dead event five additional attempts |
| GET | `/stats` | Event counts by state and total attempt count |

All routes except health require the operator bearer token. Interactive API
schemas are available at `/docs`; they do not grant access to protected routes.

Enqueue accepts `endpoint_id`, `key`, object `payload`, and optional `max_attempts`
from 1 to 20. Canonical serialized payloads are limited to 64 KiB. Identical
repeated submissions return `created: false`. Conflicting keys, disabled
endpoints, or invalid replay state return 409. Missing events return 404.

The API is not intended to accept unlimited untrusted request bodies. Set a
request-size limit at the reverse proxy if publishing it. List endpoints use
bounded offset pagination; payload bodies are omitted from event listings.
