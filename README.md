# Provider integrations

## Long-term preference retrieval and chat history

Long-term preferences remain authoritative in `user_memories`. When
`GOOGLE_API_KEY` is configured, the agent uses the separate
`GOOGLE_EMBEDDING_MODEL` setting (default `gemini-embedding-2`) to create
normalized 768-dimensional preference and query vectors. The vectors are
stored in the same relational database in `user_memory_embeddings`; retrieval
uses exact cosine similarity across at most 500 active, authorized candidates,
then combines semantic relevance with lexical relevance, importance,
confidence, and recency. Every returned ID is joined back to its current
active relational memory, so stale, deleted, or superseded vectors cannot
become prompt context. If embedding configuration or calls fail, retrieval
falls back to lexical concept expansion and does not interrupt chat.

Google receives preference text when it is indexed and the current query when
semantic retrieval runs. Gemini Embedding 2 standard currently lists text
input as free, with paid usage at $0.20 per million tokens; check
[Google's current pricing](https://ai.google.dev/gemini-api/docs/pricing) and
data terms for your account before enabling it. Without `GOOGLE_API_KEY`, the
agent continues with lexical retrieval. No Pinecone or separate vector-store
account is used.

Short-term conversation messages are persisted separately in
`conversation_messages`, scoped by tenant, authenticated user, and a hashed
session key. The latest 100 messages are loaded in insertion order. This
history is distinct from durable application workflow state and long-term
preferences.

After deploying, migrate and backfill existing active preferences:

```powershell
alembic upgrade head
python -m scripts.index_user_memories
```

The backfill is safe to rerun. It skips rows whose fingerprint, embedding
model, and dimensions are already current, resumes after interrupted runs,
and returns a non-zero exit status if rows could not be indexed. A failed
embedding write leaves the relational preference intact; the memory remains
available through lexical fallback and can be indexed on a later backfill.

## Render deployment

Set the Render web service start command to `bash start.sh`. The script runs `alembic upgrade head` before starting Uvicorn, so database migrations are applied before login or other routes access the updated models.

For the currently deployed service, run `alembic upgrade head` once from the Render Shell (or trigger a deploy after changing its start command to `bash start.sh`). The current login error indicates that the deployment database has not applied revision `d3e9a6f8b21c`, which adds `users.profile_picture_data`. After that migration finishes, restart/redeploy the web service.

## Hotels: Amadeus test search

Set `AMADEUS_CLIENT_ID` and `AMADEUS_CLIENT_SECRET` from an Amadeus account. The default `AMADEUS_BASE_URL` is `https://test.api.amadeus.com`; keep it on the test host for initial evaluation. Search uses OAuth client credentials, Hotel List by-geocode, and Hotel Offers v3. It does not call Amadeus booking endpoints. Hotel options keep the supplier hotel and offer IDs and relevant room, board, and cancellation fields.

Amadeus's Self-Service documentation describes these test API routes, while its current developer portal also reports that the Self-Service portal was decommissioned on July 17. Confirm that your existing account and credentials still have access before deployment; otherwise contact Amadeus for current access and do not treat a failed request as live inventory.

## Buses: Busbud

`BUSBUD_API_KEY` and `BUSBUD_BASE_URL` are reserved configuration values. Live search intentionally remains disabled even if set, because Busbud's public partner page requires an access request and does not publish endpoint-level integration documentation. Obtain partner approval, credentials, and the current official API reference before implementing calls.

## Trains: IRCTC authorized PSP

Train search is disabled. The adapter contract is `AuthorizedRailProvider`; implement it only for an IRCTC-authorized Principal Service Provider after receiving its official API documentation, authorization terms, and credentials. No IRCTC endpoint is assumed.

## Flights and internal booking records

Duffel flight search remains unchanged. Hotel/transport search results are offers, not reservations. Existing booking actions create application records only; they do not create supplier reservations, charge payment, or cancel supplier reservations. Supplier offer IDs must not be interpreted as booking confirmations.
