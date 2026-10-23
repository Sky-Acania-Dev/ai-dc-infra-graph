"""Read-only drafts and explicit saves of sectional ordering."""
from typing import Annotated, Literal
from pydantic import Field
from backend.schemas.routing import Record, SegmentAnnotationInput
from backend.schemas.routing_bundle_contents import BundleContentsInput, SectionEnd


class SectionOrderRequest(Record):
    span: SegmentAnnotationInput
    section_end: SectionEnd = 'SPAN'
    contents: BundleContentsInput | None = None


class JunctionOrderRequest(Record):
    node_id: str
    actual_groups: Literal[True] = True
    overrides: Annotated[list[SectionOrderRequest], Field(max_length=8)] = Field(default_factory=list)
