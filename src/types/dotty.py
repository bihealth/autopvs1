# generated by datamodel-codegen:
#   filename:  ex.json
#   timestamp: 2024-03-20T17:09:52+00:00

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Value(BaseModel):
    assembly: str
    contig: str
    pos: int
    reference_deleted: str
    alternate_inserted: str


class DottySpdiResponse(BaseModel):
    success: bool
    value: Optional[Value] = None
    message: Optional[str] = None
