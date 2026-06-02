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

From the repository root, start the FastAPI backend on localhost:

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
