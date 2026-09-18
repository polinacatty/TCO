"""Pydantic schemas for recommendation and comparison endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.catalog import ModificationRead
from app.api.schemas.tco import ComponentCode, ProfileInput, TcoYearly

WeightPreset = Literal["balanced", "cheapest", "family", "premium", "student", "business"]


class RecommendationFiltersInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    purchase_price_min_rub: int | None = Field(default=None, ge=0)
    purchase_price_max_rub: int | None = Field(default=None, ge=0)
    body_types: list[str] = Field(default_factory=list)
    drives: list[str] = Field(default_factory=list)
    fuel_types: list[str] = Field(default_factory=list)
    transmissions: list[str] = Field(default_factory=list)
    segments: list[str] = Field(default_factory=list)
    year_min: int | None = Field(default=None, ge=1980, le=2100)
    year_max: int | None = Field(default=None, ge=1980, le=2100)
    power_min_hp: int | None = Field(default=None, ge=1)
    power_max_hp: int | None = Field(default=None, ge=1)
    cargo_min_l: int | None = Field(default=None, ge=0)
    seats_min: int | None = Field(default=None, ge=1)
    body_clearance_min_mm: int | None = Field(default=None, ge=0)


class RankingWeightsInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tco_5y: float = Field(ge=0.0, le=1.0)
    purchase_price: float = Field(ge=0.0, le=1.0)
    reliability: float = Field(ge=0.0, le=1.0)
    depreciation: float = Field(ge=0.0, le=1.0)
    power: float = Field(ge=0.0, le=1.0)
    cargo: float = Field(ge=0.0, le=1.0)


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile: ProfileInput
    horizon_years: int = Field(default=5, ge=1, le=10)
    top_n: int = Field(default=10, ge=1, le=30)
    filters: RecommendationFiltersInput = Field(default_factory=RecommendationFiltersInput)
    weights_preset: WeightPreset | None = "balanced"
    weights: RankingWeightsInput | None = None
    include_kasko: bool | None = None
    # Optional labels used by calibration tests to compute NDCG@K.
    relevance_labels: dict[int, int] | None = None


class CriterionContributionRead(BaseModel):
    value: float
    normalized: float
    contribution: float


class RecommendItem(BaseModel):
    rank: int
    score: float
    is_pareto_optimal: bool
    modification: ModificationRead
    tco_total_rub: int
    decomposition: dict[str, CriterionContributionRead]
    explanation_ru: str


class RecommendMetrics(BaseModel):
    ndcg_at_k: float | None = None
    diversity_at_k: int
    coverage_ratio: float
    stability_at_k: float


class RecommendResponse(BaseModel):
    items: list[RecommendItem]
    total_candidates: int
    weights: dict[str, float]
    metrics: RecommendMetrics
    computed_at: datetime


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile: ProfileInput
    horizon_years: int = Field(default=5, ge=1, le=10)
    include_kasko: bool | None = None
    modification_ids: list[int] = Field(min_length=2, max_length=3)


class CompareComponentDelta(BaseModel):
    component: ComponentCode
    delta_rub_vs_first: int


class CompareItem(BaseModel):
    modification: ModificationRead
    total_tco_rub: int
    components_rub: dict[ComponentCode, int]
    yearly: list[TcoYearly]
    delta_total_rub_vs_first: int
    delta_components_vs_first: list[CompareComponentDelta]


class CompareResponse(BaseModel):
    items: list[CompareItem]
    computed_at: datetime


__all__ = [
    "CompareRequest",
    "CompareResponse",
    "RecommendRequest",
    "RecommendResponse",
]
