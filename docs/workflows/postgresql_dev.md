# Local PostgreSQL With Docker

This repo can run a development PostgreSQL database through Docker Desktop.

## Start PostgreSQL

```powershell
docker compose up -d postgres
```

The first run downloads the PostgreSQL image if Docker does not already have it.

## Connection String

Use this development connection string:

```text
postgresql://ai_dc_infra_graph:ai_dc_infra_graph_dev@localhost:5432/ai_dc_infra_graph
```

The matching settings are in `docker-compose.yml`:

- database: `ai_dc_infra_graph`
- user: `ai_dc_infra_graph`
- password: `ai_dc_infra_graph_dev`
- host: `localhost`
- port: `5432`

## Check Status

```powershell
docker compose ps
```

## Apply Migrations

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Import Topology Data

Use the standardized cutsheet pipeline to build normalized topology data and persist it into PostgreSQL:

```powershell
.\.venv\Scripts\python.exe .\scripts\import_topology_to_postgresql.py `
  --cutsheet-path <management-cutsheet.csv-or-ods> `
  --roce-cutsheet-path <roce-cutsheet.csv-or-ods> `
  --overhead-path <overhead.ods> `
  --overhead-sheet-name Sheet1
```

Omit `--roce-cutsheet-path` when only one cutsheet source should be imported.

## Run PostgreSQL Query Tests

The PostgreSQL integration tests are skipped by default during normal unit discovery. Run them explicitly when Docker PostgreSQL is up and migrations are applied:

```powershell
$env:RUN_POSTGRESQL_TESTS='1'
.\.venv\Scripts\python.exe -m unittest tests.integration.test_postgresql_queries
```

These tests currently cover PostgreSQL query aggregation, repository save/load, and transactional status/progress mutation persistence with operation-log writes.

## Stop PostgreSQL

```powershell
docker compose stop postgres
```

## Remove The Database Volume

Only run this when you intentionally want to delete the local development database contents:

```powershell
docker compose down -v
```

## Sharing Docker PostgreSQL With Other Projects

Docker PostgreSQL can be used for other projects. The safer pattern is one container or one database per project.

For separate containers, each project should use:

- a different Compose project directory or service/container name
- a different named volume
- a different host port if two PostgreSQL containers run at the same time

For one shared PostgreSQL container, create separate databases and users per project. This is convenient, but project-local Compose files are usually cleaner for development because they keep data, ports, and credentials isolated.
