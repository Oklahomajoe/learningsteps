# Local API integration check

`integration_local.py` runs real HTTP requests against a separate API process on
127.0.0.1:8001 inside the development container. It creates its own uniquely named
PostgreSQL database, initializes the repository schema and removes only that
database afterward. It does not clear the configured learning journal database.

The local PostgreSQL account must be able to create test databases. This is a
local development test, not a reason to grant CREATEDB to the cloud application
account.

From the application directory, with the local containers running:

```powershell
docker compose --env-file .env -p learningsteps-origins -f .devcontainer/docker-compose.yml exec -T devcontainer /workspaces/venv/bin/python /workspaces/tests/integration_local.py
```

The JSON report is written to stdout; exit code 0 means success. The report
contains synthetic data and outcomes, never database connection strings.

Coverage: all six CRUD routes, missing and malformed IDs, partial updates,
concurrent changes to different fields, rejected invalid payloads, timestamps,
API-process restart, startup/shutdown logging and journal-body exclusion from
the checked log. This does not establish Azure security or production readiness.
