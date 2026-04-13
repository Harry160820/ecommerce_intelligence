# E-commerce Customer Intelligence Platform

End-to-end MLOps project built on the Olist Brazilian E-commerce dataset.
Covers SQL analytics, churn prediction, CLV forecasting, real-time streaming,
and a Power BI executive dashboard.

---

## Tech Stack

| Layer              | Tool                                      |
|--------------------|-------------------------------------------|
| Database           | PostgreSQL 15                             |
| Data ingestion     | Kaggle API → pandas → SQLAlchemy          |
| Feature engineering| SQL window functions + Python             |
| Churn model        | XGBoost + SMOTE + SHAP explainability     |
| CLV model          | LightGBM + log-transform                  |
| Experiment tracking| MLflow                                    |
| Streaming          | Apache Kafka + Faker                      |
| Dashboard          | Power BI Desktop + Service                |
| Version control    | Git + GitHub                              |

---


## Quick Start (Windows)

```cmd
cd %USERPROFILE%\Desktop\ecommerce-intelligence
conda activate ecom
pip install -r requirements.txt
copy .env.example .env
REM Edit .env and add your Kaggle credentials
psql -U postgres -c "CREATE DATABASE ecommerce;"
psql -U ecom_user -d ecommerce -f sql\01_schema.sql
python data\load_kaggle.py
jupyter lab
```

---

## Folder Structure

```
ecommerce-intelligence\
├── .env                    ← your credentials (not on GitHub)
├── .env.example            ← template
├── .gitignore
├── README.md
├── requirements.txt
├── sql\                    ← all SQL files
├── src\                    ← Python modules (db, features, models)
├── data\                   ← data loading script
├── notebooks\              ← EDA + ML notebooks
├── streaming\              ← Kafka producer/consumer
├── powerbi\                ← DAX measures reference
├── tests\                  ← unit tests
├── docs\screenshots\       ← Power BI screenshots
└── mlruns\                 ← MLflow experiment logs
```

---

## Run Sequence

1. `psql ... -f sql\01_schema.sql`       Create all tables
2. `python data\load_kaggle.py`          Load Olist data
3. `mlflow ui --port 5000`               Start experiment tracker
4. Notebook 01 — EDA
5. Notebook 02 — Churn model
6. Notebook 03 — CLV model
7. `psql ... -f sql\05_product_affinity.sql`  Run after ML predictions exist
8. `python streaming\producer.py`        Start live order stream

---

## Author
- **Hari Om**

Hari Om | [GitHub](https://github.com/harry160820) | [Upwork](https://www.upwork.com/freelancers/~01312454b54d248320)
