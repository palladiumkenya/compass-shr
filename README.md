# compass-shr

A Shared Health Record (SHR) system built on [HAPI FHIR](https://hapifhir.io/) R4, with JWT authentication and an nginx API gateway.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| `nginx` | 80 | API gateway |
| `compass-auth` | 7777 | JWT authentication |
| `fhir` | 8080 | HAPI FHIR R4 server |
| `db` | internal | PostgreSQL 15 |

## Setup

Copy and fill in the environment files:

```bash
cp .env.example .env
cp fhir.env.example fhir.env
cp auth_settings.env.example auth_settings.env
```

The HMAC secret in `fhir.env` (`HAPI_FHIR_AUTH_JWT_SECRET`) must match the `key` field of the client entry in `auth_settings.env`.

## Running

```bash
docker compose up -d
```

On first run, a `seeder` service loads Kenyan facility data from `fhir/all_emr_sites.csv` into the FHIR server as `Organization` resources. It skips automatically on subsequent runs.

## API

All requests go through nginx on port 80.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/hie-auth?key=<key>` | GET | Obtain a JWT token |
| `/v1/shr-submission?resource=ServiceRequest` | POST | Submit a ServiceRequest |
| `/v1/shr-referrals?facility_code=<mfl>` | GET | Fetch referrals for a facility |

All FHIR requests require `Authorization: Bearer <token>`.

### Get a token

```bash
curl -u username:password "http://localhost/v1/hie-auth?key=<client-key>"
```

### Submit a ServiceRequest

```bash
curl -X POST "http://localhost/v1/shr-submission?resource=ServiceRequest" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/fhir+json" \
  -d @payload.json
```

### Fetch referrals by facility

```bash
curl "http://localhost/v1/shr-referrals?facility_code=14868" \
  -H "Authorization: Bearer <token>"
```
