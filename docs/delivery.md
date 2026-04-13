# Delivery behavior

A transaction inserts a single event for each endpoint and idempotency key.
Reusing a key with a different canonical JSON payload returns a conflict.
Changing object key order does not create a new event.

Workers claim pending rows with `BEGIN IMMEDIATE`, assign a random lease token
and insert an attempt row. They perform HTTP outside the transaction. A worker
may finish only the claim whose token it owns. Expired leases become retries or
dead events according to the remaining attempt budget. Attempt rows survive
replay; replay extends the budget by five more attempts.

Delivery is **at least once**. A receiver may accept a request immediately before
a worker dies. The next worker sends it again. Receivers must deduplicate the
`X-Hookline-Id` header. Disabling an endpoint pauses unclaimed work; it cannot
recall a request already in flight.

Any 2xx response succeeds. Connection errors, 408, 429 and 5xx retry with bounded
exponential jitter. Other statuses, including redirects, become dead events.
The worker does not follow redirects, use environment proxies, or store response
bodies. `Retry-After` is not currently supported. The HTTP timeout applies to
socket operations, not an absolute wall-clock deadline.

The signature is hex HMAC-SHA256 over `timestamp + "." + raw_body`, using the
endpoint secret. Verify the signature over the original bytes and reject old
requests. `examples.receiver` demonstrates the procedure. Do not reserialize
JSON before verification.

This is a single-operator service. Its bearer token grants all administration
rights. Destination hostnames must be explicitly allowed. Allowlisting is an
operator guardrail, not a sandbox against a hostile administrator or DNS owner;
use network egress controls if those are in scope. Secrets are stored in the
local database, so protect backups and filesystem permissions. Use a TLS reverse
proxy before exposing the API beyond a trusted local network.

SQLite is suitable for one host with a small number of workers. Do not share
its volume across hosts or network filesystems. There is no automatic retention,
tenant isolation, PostgreSQL backend or distributed broker.
