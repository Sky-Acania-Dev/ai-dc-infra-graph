# Development Workflow

## Python Environment

Use the project virtual environment from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If unit tests are needed and `pytest` is not installed, either install it into the venv or run the standard-library test runner:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

## Prepare PostgreSQL Database

Docker Desktop must be running. Start the repo-local PostgreSQL container:

```powershell
docker compose up -d postgres
```

Apply migrations:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

If the database is empty or you want to refresh it from the source spreadsheets, import topology data into PostgreSQL:

```powershell
.\.venv\Scripts\python.exe .\scripts\import_topology_to_postgresql.py `
  --cutsheet-path "C:\Personal Folder\Work\Megawatt\OK Muskogee\CUTSHEET.ods" `
  --roce-cutsheet-path "C:\Personal Folder\Work\Megawatt\OK Muskogee\CUTSHEET ROCE FULL.ods" `
  --roce-cutsheet-sheet-name "DH1 NODE TO TIER-0" `
  --roce-cutsheet-sheet-name "DH2 NODE TO TIER-0" `
  --roce-cutsheet-sheet-name "DH1,DH2 TIER-0 TO TIER-1" `
  --overhead-path "C:\Personal Folder\Work\Megawatt\OK Muskogee\OVERHEAD.ods"
```

The development database URL is provided by `docker-compose.yml`:

```text
postgresql://ai_dc_infra_graph:ai_dc_infra_graph_dev@localhost:5432/ai_dc_infra_graph
```

By default the import uses:

- Project UID: `MSK01`
- Building ID: `A`
- Status overrides: `data/status_overrides.json`
- Default cabinet size: `48U`

## Manual Status Overrides

Status overrides live in `data/status_overrides.json`. Use `data/status_overrides.example.json` as the format reference.

Supported override areas:

- data hall lifecycle status
- cabinet lifecycle status
- cabinet max RU count
- device lifecycle/model/note placeholders
- cable progress, length, and note by cable UID

## Run Backend

From the repository root, start the FastAPI backend on localhost. PostgreSQL is the default storage backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Backend URL:

```text
http://127.0.0.1:8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

To force the legacy JSON backend for debugging or rollback:

```powershell
$env:TOPOLOGY_STORAGE_BACKEND = "json"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## Legacy JSON Runtime

Use this only when you deliberately want to run the old JSON-backed development path.

Build the normalized runtime JSON from the source cutsheet and overhead files:

```powershell
.\.venv\Scripts\python.exe scripts\build_database.py `
  --cutsheet-path "C:\Personal Folder\Work\Megawatt\OK Muskogee\CUTSHEET.ods" `
  --roce-cutsheet-path "C:\Personal Folder\Work\Megawatt\OK Muskogee\CUTSHEET ROCE FULL.ods" `
  --roce-cutsheet-sheet-name "DH1 NODE TO TIER-0" `
  --roce-cutsheet-sheet-name "DH2 NODE TO TIER-0" `
  --roce-cutsheet-sheet-name "DH1,DH2 TIER-0 TO TIER-1" `
  --overhead-path "C:\Personal Folder\Work\Megawatt\OK Muskogee\OVERHEAD.ods" `
  --runtime-path data\runtime\current_database.json
```

Load an existing normalized runtime snapshot without re-ingesting source spreadsheets:

```powershell
.\.venv\Scripts\python.exe scripts\load_database.py data\runtime\current_database.json.bak --runtime-path data\runtime\current_database.json
```

Do not use legacy cutsheet-only exports such as `data\exports\cutsheet_full.json` when refreshing active runtime data.
Those exports do not ingest the RoCE cutsheet. Use `scripts\build_database.py` with `--roce-cutsheet-path` instead.

See `docs\workflows\postgresql_dev.md` for more Docker PostgreSQL notes, including integration tests, stopping the container, deleting the local volume, and using Docker PostgreSQL for other projects.

## Run Frontend

For active frontend development, run the Vite dev server from `frontend/web`:

```powershell
npm install
npm run dev
```

Frontend dev URL:

```text
http://127.0.0.1:5173
```

Production build:

```powershell
npm run build
```

To serve the built frontend locally with the same localhost URL, run this from the repository root after `npm run build`:

```powershell
.\.venv\Scripts\python.exe -m http.server 5173 --bind 127.0.0.1 --directory frontend\web\dist
```

Built frontend URL:

```text
http://127.0.0.1:5173
```

The frontend expects the backend API at `http://127.0.0.1:8000` unless `VITE_API_BASE_URL` is set.

## Fixture Data

Test fixtures live in `tests/fixtures/`.

- `cutsheet_sample.ods`: sample source cutsheet fixture.
- `overhead_fake.json`: small fake overhead inventory with two cabinet rows, one core cabinet, three end-row nodes, two storage nodes, and GPU cabinets for the rest.
