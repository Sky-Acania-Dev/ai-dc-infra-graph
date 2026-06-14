from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import router as auth_router
from backend.api.database import router as database_router
from backend.api.tasks import router as tasks_router
from backend.api.topology import router as topology_router
from backend.api.validation import router as validation_router


app = FastAPI(title="AI DC Infra Graph")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://100.121.214.15:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(database_router)
app.include_router(auth_router)
app.include_router(topology_router)
app.include_router(tasks_router)
app.include_router(validation_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
