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

## Build Runtime Database

Build the normalized runtime JSON from the source cutsheet and overhead files:

```powershell
.\.venv\Scripts\python.exe scripts\build_database.py `
  --cutsheet-path "C:\Personal Folder\Work\Megawatt\OK Muskogee\CUTSHEET.ods" `
  --overhead-path "C:\Personal Folder\Work\Megawatt\OK Muskogee\OVERHEAD.ods" `
  --runtime-path data\runtime\current_database.json
```

By default the build uses:

- Project UID: `MSK01`
- Building ID: `A`
- Status overrides: `data/status_overrides.json`
- Default cabinet size: `48U`

## Load Existing Runtime JSON

Use this when you already have a normalized JSON and do not want to re-ingest source spreadsheets:

```powershell
.\.venv\Scripts\python.exe scripts\load_database.py data\exports\cutsheet_full.json --runtime-path data\runtime\current_database.json
```

## Manual Status Overrides

Status overrides live in `data/status_overrides.json`. Use `data/status_overrides.example.json` as the format reference.

Supported override areas:

- data hall lifecycle status
- cabinet lifecycle status
- cabinet max RU count
- device lifecycle/model/note placeholders
- cable progress, length, and note by cable UID

## Run Backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Run Frontend

From `frontend/web`:

```powershell
npm install
npm run dev
```

Production build:

```powershell
npm run build
```

## Fixture Data

Test fixtures live in `tests/fixtures/`.

- `cutsheet_sample.ods`: sample source cutsheet fixture.
- `overhead_fake.json`: small fake overhead inventory with two cabinet rows, one core cabinet, three end-row nodes, two storage nodes, and GPU cabinets for the rest.
