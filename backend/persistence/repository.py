from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from backend.persistence.json_database import load_topology_database, save_topology_database
from backend.persistence.json_database import TopologyDatabase


class TopologyRepository(ABC):
    @abstractmethod
    def load(self) -> TopologyDatabase:
        raise NotImplementedError

    @abstractmethod
    def save(self, database: TopologyDatabase) -> None:
        raise NotImplementedError


class JsonTopologyRepository(TopologyRepository):
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> TopologyDatabase:
        return load_topology_database(self.path)

    def save(self, database: TopologyDatabase) -> None:
        save_topology_database(database, self.path)
