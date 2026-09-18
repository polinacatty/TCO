# ml/

Каталог для всех ML- и data-pipeline артефактов проекта.

## Структура

```
ml/
├── data/
│   ├── seed/          ← статические курируемые справочники
│   ├── raw/           ← сырые выгрузки из источников
│   └── processed/     ← очищенные таблицы
├── pipelines/         ← ETL-скрипты на Python
├── notebooks/         ← Jupyter ноутбуки для EDA, прототипов моделей
└── README.md
```

## Запуск пайплайнов

```
# Загрузка цен на топливо за указанный период
python -m ml.pipelines.ingest_fuel_prices --start 2014-01 --end 2026-04

# Загрузка курсов ЦБ
python -m ml.pipelines.ingest_cbr_rates --start 2014-01-01

# Запуск всех ETL последовательно
make ingest-all
```
