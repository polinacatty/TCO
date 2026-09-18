from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Catalog                                                            #
    # ------------------------------------------------------------------ #
    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("iso_code", sa.String(length=8), nullable=False),
        sa.Column("federal_district", sa.String(length=64), nullable=False),
        sa.Column("climate_zone", sa.String(length=32), nullable=False),
        sa.Column("population_thousands", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_regions"),
        sa.UniqueConstraint("name", name="uq_regions_name"),
    )

    op.create_table(
        "car_makes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("name_normalized", sa.String(length=64), nullable=False),
        sa.Column("country", sa.String(length=64), nullable=False),
        sa.Column("brand_tier", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_car_makes"),
        sa.UniqueConstraint("name", name="uq_car_makes_name"),
    )
    op.create_index("ix_car_makes_name_normalized", "car_makes", ["name_normalized"])
    op.create_index("ix_car_makes_brand_tier", "car_makes", ["brand_tier"])

    op.create_table(
        "car_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("make_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("name_normalized", sa.String(length=64), nullable=False),
        sa.Column("segment", sa.String(length=16), nullable=False),
        sa.Column("body_type", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["make_id"], ["car_makes.id"],
            name="fk_car_models_make_id_car_makes", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_car_models"),
    )
    op.create_index("ix_car_models_make_id", "car_models", ["make_id"])
    op.create_index("ix_car_models_name_normalized", "car_models", ["name_normalized"])
    op.create_index("ix_car_models_segment", "car_models", ["segment"])

    op.create_table(
        "car_generations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("year_from", sa.SmallInteger(), nullable=False),
        sa.Column("year_to", sa.SmallInteger(), nullable=True),
        sa.Column("restyling", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["model_id"], ["car_models.id"],
            name="fk_car_generations_model_id_car_models", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_car_generations"),
    )
    op.create_index("ix_car_generations_model_id", "car_generations", ["model_id"])

    op.create_table(
        "car_modifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generation_id", sa.Integer(), nullable=False),
        sa.Column("trim_name", sa.String(length=128), nullable=True),
        sa.Column("engine_volume_l", sa.Float(), nullable=False),
        sa.Column("power_hp", sa.SmallInteger(), nullable=False),
        sa.Column("torque_nm", sa.SmallInteger(), nullable=True),
        sa.Column("fuel_type", sa.String(length=16), nullable=False),
        sa.Column("transmission", sa.String(length=16), nullable=False),
        sa.Column("drive", sa.String(length=16), nullable=False),
        sa.Column("fuel_consumption_combined_l_100km", sa.Float(), nullable=False),
        sa.Column("fuel_consumption_city_l_100km", sa.Float(), nullable=True),
        sa.Column("fuel_consumption_highway_l_100km", sa.Float(), nullable=True),
        sa.Column("length_mm", sa.Integer(), nullable=True),
        sa.Column("width_mm", sa.Integer(), nullable=True),
        sa.Column("height_mm", sa.Integer(), nullable=True),
        sa.Column("curb_weight_kg", sa.Integer(), nullable=True),
        sa.Column("seats", sa.SmallInteger(), nullable=True),
        sa.Column("cargo_volume_l", sa.Integer(), nullable=True),
        sa.Column("body_clearance_mm", sa.Integer(), nullable=True),
        sa.Column("msrp_new_rub", sa.Integer(), nullable=False),
        sa.Column("reliability_score", sa.Float(), nullable=False),
        sa.Column("msrp_source", sa.String(length=64), nullable=True),
        sa.Column("reliability_source", sa.String(length=64), nullable=True),
        sa.Column("enriched_at", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(
            ["generation_id"], ["car_generations.id"],
            name="fk_car_modifications_generation_id_car_generations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_car_modifications"),
    )
    op.create_index(
        "ix_car_modifications_generation_id", "car_modifications", ["generation_id"]
    )
    op.create_index("ix_car_modifications_fuel_type", "car_modifications", ["fuel_type"])
    op.create_index("ix_car_modifications_power_hp", "car_modifications", ["power_hp"])

    op.create_table(
        "tire_sizes",
        sa.Column("modification_id", sa.Integer(), nullable=False),
        sa.Column("axle", sa.String(length=8), nullable=False),
        sa.Column("size_code", sa.String(length=16), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["modification_id"], ["car_modifications.id"],
            name="fk_tire_sizes_modification_id_car_modifications",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("modification_id", "axle", name="pk_tire_sizes"),
    )
    op.create_index("ix_tire_sizes_modification_id", "tire_sizes", ["modification_id"])

    op.create_table(
        "tire_size_prices",
        sa.Column("size_code", sa.String(length=16), nullable=False),
        sa.Column("season", sa.String(length=8), nullable=False),
        sa.Column("avg_set_price_rub", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("size_code", "season", name="pk_tire_size_prices"),
    )

    # ------------------------------------------------------------------ #
    # Pricing: ОСАГО                                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "osago_base_tariffs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("category_label", sa.String(length=128), nullable=False),
        sa.Column("vehicle_categories", sa.String(length=64), nullable=False),
        sa.Column("owner_type", sa.String(length=32), nullable=False),
        sa.Column("tb_min_rub", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("tb_max_rub", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_osago_base_tariffs"),
    )
    op.create_table(
        "osago_territory_coefs",
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("region_name", sa.String(length=128), nullable=False),
        sa.Column("kt_capital_city", sa.String(length=128), nullable=True),
        sa.Column("kt_general", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("kt_special", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("source_ref", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"],
            name="fk_osago_territory_coefs_region_id_regions", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("region_id", name="pk_osago_territory_coefs"),
    )
    op.create_table(
        "osago_power",
        sa.Column("vehicle_family", sa.String(length=32), nullable=False),
        sa.Column("power_min_hp_excl", sa.Integer(), nullable=False),
        sa.Column("power_max_hp_incl", sa.Integer(), nullable=False),
        sa.Column("km_value", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.PrimaryKeyConstraint(
            "vehicle_family", "power_min_hp_excl", "power_max_hp_incl",
            name="pk_osago_power",
        ),
    )
    op.create_table(
        "osago_kbm",
        sa.Column("kbm_class", sa.String(length=2), nullable=False),
        sa.Column("kbm_value", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("class_after_no_claim", sa.String(length=2), nullable=False),
        sa.Column("class_after_1_claim", sa.String(length=2), nullable=False),
        sa.Column("class_after_2_claims", sa.String(length=2), nullable=False),
        sa.Column("class_after_3_claims", sa.String(length=2), nullable=False),
        sa.Column("class_after_more_than_3_claims", sa.String(length=2), nullable=False),
        sa.PrimaryKeyConstraint("kbm_class", name="pk_osago_kbm"),
    )
    op.create_table(
        "osago_age_exp",
        sa.Column("vehicle_family", sa.String(length=32), nullable=False),
        sa.Column("age_min_incl", sa.SmallInteger(), nullable=False),
        sa.Column("age_max_incl", sa.SmallInteger(), nullable=False),
        sa.Column("exp_min_years_incl", sa.SmallInteger(), nullable=False),
        sa.Column("exp_max_years_excl", sa.SmallInteger(), nullable=False),
        sa.Column("kvs_value", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.PrimaryKeyConstraint(
            "vehicle_family", "age_min_incl", "exp_min_years_incl",
            name="pk_osago_age_exp",
        ),
    )
    op.create_table(
        "osago_drivers",
        sa.Column("restricted", sa.Boolean(), nullable=False),
        sa.Column("owner_type", sa.String(length=32), nullable=False),
        sa.Column("ko_value", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("restricted", "owner_type", name="pk_osago_drivers"),
    )
    op.create_table(
        "osago_seasonal",
        sa.Column("period_min_months_excl", sa.SmallInteger(), nullable=False),
        sa.Column("period_max_months_incl", sa.SmallInteger(), nullable=False),
        sa.Column("ks_value", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.PrimaryKeyConstraint(
            "period_min_months_excl", "period_max_months_incl",
            name="pk_osago_seasonal",
        ),
    )

    # ------------------------------------------------------------------ #
    # Pricing: налоги                                                    #
    # ------------------------------------------------------------------ #
    op.create_table(
        "transport_tax_rates",
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("hp_min", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("hp_max", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("rate_rub_per_hp", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"],
            name="fk_transport_tax_rates_region_id_regions", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("region_id", "hp_min", name="pk_transport_tax_rates"),
    )
    op.create_table(
        "luxury_cars",
        sa.Column("make", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=False),
        sa.Column("engine_type", sa.String(length=32), nullable=True),
        sa.Column("engine_volume_l", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("price_tier_min_rub", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint(
            "make", "model", "price_tier_min_rub", name="pk_luxury_cars"
        ),
    )

    # ------------------------------------------------------------------ #
    # Pricing: амортизация                                               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "depreciation_rates",
        sa.Column("segment", sa.String(length=16), nullable=False),
        sa.Column("brand_tier", sa.String(length=32), nullable=False),
        sa.Column("age_year_bucket", sa.SmallInteger(), nullable=False),
        sa.Column("annual_depreciation_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint(
            "segment", "brand_tier", "age_year_bucket", name="pk_depreciation_rates"
        ),
    )
    op.create_table(
        "mileage_penalties",
        sa.Column("mileage_threshold_km", sa.Integer(), nullable=False),
        sa.Column("extra_depreciation_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("mileage_threshold_km", name="pk_mileage_penalties"),
    )

    # ------------------------------------------------------------------ #
    # Pricing: КАСКО                                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "kasko_rates",
        sa.Column("brand_tier", sa.String(length=32), nullable=False),
        sa.Column("segment", sa.String(length=16), nullable=False),
        sa.Column("age_year_bucket", sa.SmallInteger(), nullable=False),
        sa.Column("kasko_rate_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.PrimaryKeyConstraint(
            "brand_tier", "segment", "age_year_bucket", name="pk_kasko_rates"
        ),
    )

    # ------------------------------------------------------------------ #
    # Pricing: плановое ТО                                               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "service_operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("default_norm_hours", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_service_operations"),
        sa.UniqueConstraint("code", name="uq_service_operations_code"),
    )
    op.create_index("ix_service_operations_category", "service_operations", ["category"])

    op.create_table(
        "service_plan_ops",
        sa.Column("generation_id", sa.Integer(), nullable=False),
        sa.Column("operation_id", sa.Integer(), nullable=False),
        sa.Column("every_km", sa.Integer(), nullable=True),
        sa.Column("every_months", sa.SmallInteger(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["generation_id"], ["car_generations.id"],
            name="fk_service_plan_ops_generation_id_car_generations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"], ["service_operations.id"],
            name="fk_service_plan_ops_operation_id_service_operations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "generation_id", "operation_id", name="pk_service_plan_ops"
        ),
    )
    op.create_index(
        "ix_service_plan_ops_generation_id", "service_plan_ops", ["generation_id"]
    )

    op.create_table(
        "parts_costs",
        sa.Column("operation_id", sa.Integer(), nullable=False),
        sa.Column("operation_code", sa.String(length=64), nullable=False),
        sa.Column("brand_segment", sa.String(length=32), nullable=False),
        sa.Column("avg_parts_cost_rub", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["operation_id"], ["service_operations.id"],
            name="fk_parts_costs_operation_id_service_operations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("operation_id", "brand_segment", name="pk_parts_costs"),
    )
    op.create_table(
        "labor_rates",
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("region_name", sa.String(length=128), nullable=False),
        sa.Column("sto_type", sa.String(length=16), nullable=False),
        sa.Column("rate_rub_per_hour", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"],
            name="fk_labor_rates_region_id_regions", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("region_id", "sto_type", name="pk_labor_rates"),
    )

    # ------------------------------------------------------------------ #
    # Pricing: топливо                                                   #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fuel_prices",
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("fuel_type", sa.String(length=16), nullable=False),
        sa.Column("price_month", sa.Date(), nullable=False),
        sa.Column("price_rub_per_l", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"],
            name="fk_fuel_prices_region_id_regions", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "region_id", "fuel_type", "price_month", name="pk_fuel_prices"
        ),
    )

    op.create_table(
        "fuel_price_forecast",
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("fuel_type", sa.String(length=16), nullable=False),
        sa.Column("price_month", sa.Date(), nullable=False),
        sa.Column("price_rub_per_l", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("forecast_origin_month", sa.Date(), nullable=False),
        sa.Column("horizon_step", sa.SmallInteger(), nullable=False),
        sa.Column("model_version", sa.String(length=16), nullable=False),
        sa.Column("fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"],
            name="fk_fuel_price_forecast_region_id_regions", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "region_id", "fuel_type", "price_month", name="pk_fuel_price_forecast"
        ),
    )

    # ------------------------------------------------------------------ #
    # Pricing: ЦБ                                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "cbr_rates",
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("metric_type", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("metric_date", "metric_type", name="pk_cbr_rates"),
    )

    # ------------------------------------------------------------------ #
    # ML registries                                                      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "ml_models_registry",
        sa.Column("model_type", sa.String(length=32), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("region_name", sa.String(length=128), nullable=False),
        sa.Column("fuel_type", sa.String(length=16), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("train_mape_pct", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("train_rmse", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("train_mae", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("train_coverage_95_pct", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("train_window_start", sa.String(length=10), nullable=True),
        sa.Column("train_window_end", sa.String(length=10), nullable=True),
        sa.Column("test_window_start", sa.String(length=10), nullable=True),
        sa.Column("test_window_end", sa.String(length=10), nullable=True),
        sa.Column("order_p", sa.SmallInteger(), nullable=True),
        sa.Column("order_d", sa.SmallInteger(), nullable=True),
        sa.Column("order_q", sa.SmallInteger(), nullable=True),
        sa.Column("seasonal_p", sa.SmallInteger(), nullable=True),
        sa.Column("seasonal_d", sa.SmallInteger(), nullable=True),
        sa.Column("seasonal_q", sa.SmallInteger(), nullable=True),
        sa.Column("seasonal_period", sa.SmallInteger(), nullable=True),
        sa.Column("aic", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("bic", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fit_seconds", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("fitted_at", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"],
            name="fk_ml_models_registry_region_id_regions", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "model_type", "region_id", "fuel_type", "version",
            name="pk_ml_models_registry",
        ),
    )
    op.create_table(
        "ml_strategies_registry",
        sa.Column("model_type", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("algorithm", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("criteria_count", sa.SmallInteger(), nullable=True),
        sa.Column("has_artifact", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("artifact_path", sa.Text(), nullable=True),
        sa.Column("ndcg_at_10_median", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("diversity_at_10_median", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("coverage_pct", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("stability_median", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("target_ndcg", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("target_diversity", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("target_coverage_pct", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("target_stability", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("validator_path", sa.Text(), nullable=True),
        sa.Column("methodology_doc", sa.Text(), nullable=True),
        sa.Column("validation_set_path", sa.Text(), nullable=True),
        sa.Column("last_validated_at", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.PrimaryKeyConstraint(
            "model_type", "version", name="pk_ml_strategies_registry"
        ),
    )


def downgrade() -> None:
    op.drop_table("ml_strategies_registry")
    op.drop_table("ml_models_registry")
    op.drop_table("cbr_rates")
    op.drop_table("fuel_price_forecast")
    op.drop_table("fuel_prices")
    op.drop_table("labor_rates")
    op.drop_table("parts_costs")
    op.drop_index("ix_service_plan_ops_generation_id", table_name="service_plan_ops")
    op.drop_table("service_plan_ops")
    op.drop_index("ix_service_operations_category", table_name="service_operations")
    op.drop_table("service_operations")
    op.drop_table("kasko_rates")
    op.drop_table("mileage_penalties")
    op.drop_table("depreciation_rates")
    op.drop_table("luxury_cars")
    op.drop_table("transport_tax_rates")
    op.drop_table("osago_seasonal")
    op.drop_table("osago_drivers")
    op.drop_table("osago_age_exp")
    op.drop_table("osago_kbm")
    op.drop_table("osago_power")
    op.drop_table("osago_territory_coefs")
    op.drop_table("osago_base_tariffs")
    op.drop_table("tire_size_prices")
    op.drop_index("ix_tire_sizes_modification_id", table_name="tire_sizes")
    op.drop_table("tire_sizes")
    op.drop_index("ix_car_modifications_power_hp", table_name="car_modifications")
    op.drop_index("ix_car_modifications_fuel_type", table_name="car_modifications")
    op.drop_index("ix_car_modifications_generation_id", table_name="car_modifications")
    op.drop_table("car_modifications")
    op.drop_index("ix_car_generations_model_id", table_name="car_generations")
    op.drop_table("car_generations")
    op.drop_index("ix_car_models_segment", table_name="car_models")
    op.drop_index("ix_car_models_name_normalized", table_name="car_models")
    op.drop_index("ix_car_models_make_id", table_name="car_models")
    op.drop_table("car_models")
    op.drop_index("ix_car_makes_brand_tier", table_name="car_makes")
    op.drop_index("ix_car_makes_name_normalized", table_name="car_makes")
    op.drop_table("car_makes")
    op.drop_table("regions")
