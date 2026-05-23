from pydantic import BaseModel


class AffectedRange(BaseModel):
    introduced: str | None = None
    fixed: str | None = None


class Advisory(BaseModel):
    id: str
    aliases: list[str]
    summary: str
    details: str
    severity: str | None
    affected_ranges: list[AffectedRange]
    fixed_version: str | None
    published: str | None
    references: list[str]
    package: str
    ecosystem: str
