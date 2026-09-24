from typing import Any, Literal

from pydantic import BaseModel, Field


class AssetInfo(BaseModel):
    gold_grams: float | None = Field(default=None, ge=0, le=5000)
    land_acres: float | None = Field(default=None, ge=0, le=1000)
    house: bool = False
    fd_amount: int | None = Field(default=None, ge=0, le=100_000_000)


class EligibilityRequest(BaseModel):
    session_id: str
    assets: AssetInfo = AssetInfo()
    occupation: Literal["farmer", "business", "salaried", "pensioner", "student", "other"]
    purpose: Literal["farming", "business", "education", "home", "medical", "personal", "not_sure"]
    age: int = Field(ge=18, le=110)


class Reason(BaseModel):
    code: str
    params: dict[str, Any] = {}


class SchemeSource(BaseModel):
    name: str
    url: str | None = None


class SchemeMatch(BaseModel):
    scheme_id: str
    kind: str
    name: str
    name_english: str
    summary: str
    status: Literal["likely", "possible"]
    collateral_free: bool
    reasons: list[Reason]
    estimate: dict[str, Any] | None = None
    documents: list[str]
    source: SchemeSource
    is_new: bool = False
    added_on: str | None = None


class EligibilityResponse(BaseModel):
    matches: list[SchemeMatch]
    catalogue_version: str
    requires_human_review: bool = True
