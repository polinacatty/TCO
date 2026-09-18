"""CriterionSpec — описание критерия для TOPSIS / WSM."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriterionSpec:
    """Спецификация критерия ранжирования.

    Attributes:
        name: имя колонки с числовым значением критерия
        direction: 'maximize' или 'minimize'
        label_ru: подпись для UI (русская)
        unit: единица измерения для UI
    """

    name: str
    direction: str
    label_ru: str
    unit: str = ""

    def __post_init__(self) -> None:
        if self.direction not in {"maximize", "minimize"}:
            raise ValueError(
                f"direction must be 'maximize' or 'minimize', got {self.direction!r}"
            )


DEFAULT_CRITERIA: list[CriterionSpec] = [
    CriterionSpec("tco_5y", "minimize", "Стоимость владения 5 лет", "₽"),
    CriterionSpec("purchase_price", "minimize", "Цена покупки", "₽"),
    CriterionSpec("reliability_score", "maximize", "Надёжность", ""),
    CriterionSpec("depreciation_5y_pct", "minimize", "Амортизация за 5 лет", "%"),
    CriterionSpec("power_hp", "maximize", "Мощность", "л.с."),
    CriterionSpec("cargo_volume_l", "maximize", "Багажник", "л"),
]
