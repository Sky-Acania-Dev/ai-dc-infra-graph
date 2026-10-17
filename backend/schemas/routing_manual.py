from typing import Annotated

from pydantic import Field, model_validator
from backend.schemas.routing import Record, Tier

Identifier = Annotated[str, Field(min_length=1, max_length=300)]
Chain = Annotated[list[Identifier], Field(max_length=4000)]


class ManualPreviewInput(Record):
    group_uid: Identifier
    prefix_segment_ids: Chain = Field(default_factory=list)
    topology_revision: str | None = None
    start_tier: Tier = 1
    end_tier: Tier = 1


class ManualGroupUpdate(Record):
    group_uid: Identifier
    expected_version: str | None
    segment_ids: Chain
    start_tier: Tier = 1
    end_tier: Tier = 1


class ManualBatchInput(Record):
    topology_revision: Identifier
    groups: Annotated[list[ManualGroupUpdate], Field(min_length=1, max_length=200)]
    notes: Annotated[str, Field(max_length=2000)] = ''

    @model_validator(mode='after')
    def unique_groups(self):
        if len({g.group_uid for g in self.groups}) != len(self.groups):
            raise ValueError('Select each cable group once per batch.')
        return self
