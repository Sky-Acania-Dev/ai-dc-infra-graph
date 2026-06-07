from __future__ import annotations

import os


DEFAULT_DATABASE_URL = "postgresql+psycopg://ai_dc_infra_graph:ai_dc_infra_graph_dev@localhost:5432/ai_dc_infra_graph"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
