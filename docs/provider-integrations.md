# Travel search providers

## Amadeus hotels

Hotel search uses Amadeus Self-Service Hotel List by-geocode and Hotel Offers v3, and performs search requests only. It does not create or modify supplier reservations. Configure `AMADEUS_CLIENT_ID` and `AMADEUS_CLIENT_SECRET` in the backend environment. `AMADEUS_BASE_URL` defaults to `https://test.api.amadeus.com`; leave it there for test-environment searches. The application obtains and caches an OAuth client-credentials token and labels returned offers as test-environment data. Destination coordinates must come from the application's resolved destination.

The Amadeus Self-Service portal documentation reports that the portal was decommissioned on July 17, 2026. Existing account credentials/access may therefore be needed; confirm account access and current API availability with Amadeus before deployment. No live credential validation is performed by this project.

## Busbud

Live Busbud search is intentionally disabled. The public partner information does not provide the endpoint and authentication contract needed for a safe implementation. Obtain partner approval, account-specific credentials, and official integration documentation first. `BUSBUD_API_KEY` and `BUSBUD_BASE_URL` are placeholders and do not activate the provider.

## Rail / IRCTC Principal Service Provider

The project exposes a disabled provider boundary only. Integration requires an authorized PSP relationship, credentials, and official search API documentation. No unofficial IRCTC endpoints are called.

## Duffel flights and internal records

Existing Duffel flight search is preserved. Search offers remain supplier offers, while bookings created by the application are internal records. Hotel search results likewise remain offers; the existing hotel booking flow creates an internal record and does not reserve a room with Amadeus.

Add credentials through the hosting provider's secret environment configuration. Do not commit credentials or put them in frontend variables. Redeploy the backend after setting values. No migration is needed for this provider integration.
