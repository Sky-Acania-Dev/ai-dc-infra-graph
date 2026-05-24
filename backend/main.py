from fastapi import FastAPI


app = FastAPI(title="AI DC Infra Graph")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
