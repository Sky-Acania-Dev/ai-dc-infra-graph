from fastapi import FastAPI

from backend.api.validation import router as validation_router


app = FastAPI(title="AI DC Infra Graph")
app.include_router(validation_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
