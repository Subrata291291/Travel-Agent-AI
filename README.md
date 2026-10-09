# Provider integrations

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
