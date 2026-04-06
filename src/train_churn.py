"""
XGBoost churn classifier.
Logs metrics and artifacts to MLflow.
Writes predictions back to PostgreSQL (ml_churn_predictions table).
 
From notebook:  from src.train_churn import train_churn_model
"""

import os
import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")   # non-interactive backend for Windows
import matplotlib.pyplot as plt

import mlflow
import mlflow.xgboost
import xgboost as xgb
import shap
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import (roc_auc_score, classification_report,
                             confusion_matrix, ConfusionMatrixDisplay)

from imblearn.over_sampling import SMOTE
 
from src.features import build_feature_matrix, get_rfm_segments, FEATURE_COLS, CHURN_TARGET
from src.db import engine

load_dotenv()   # load environment variables from .env file

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment("ecommerce-churn-prediction")

def train_churn_model():
    """Complete churn training pipeline. Returns trained XGBoost model."""

    # 1. data
    print("=" * 50)
    print("CHURN MODEL TRAINING")
    print("=" * 50)
    print("\n[1/5] Building feature matrix ...")
    df = build_feature_matrix()
    df = get_rfm_segments(df)

    X = df[FEATURE_COLS]
    y = df[CHURN_TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # 2. Balance classes with SMOTE
    print("[2/5] Applying SMOTE ...")
    X_train_sm, y_train_sm = SMOTE(random_state=42).fit_resample(X_train, y_train)
    print(f"Train samples after SMOTE: {len(X_train_sm):,}")

    # 3. Train XGBoost

    print("[3/5] Training XGBoost ...")
    params = {
        "n_estimators":          400,
        "max_depth":             5,
        "learning_rate":         0.05,
        "subsample":             0.8,
        "colsample_bytree":      0.8,
        "min_child_weight":      3,
        "gamma":                 0.1,
        "reg_alpha":             0.1,
        "reg_lambda":            1.0,
        "random_state":          42,
        "eval_metric":           "auc",
        "early_stopping_rounds": 30,
    }

    with mlflow.start_run(run_name="xgboost-churn-v1"):
        mlflow.log_params(params)
        mlflow.log_param("smote", True)
        mlflow.log_param("train_n", len(X_train_sm))
        mlflow.log_param("test_n",  len(X_test))
 
        model = xgb.XGBClassifier(**params)
        model.fit(X_train_sm, y_train_sm,
                  eval_set=[(X_test, y_test)],
                  verbose=False)
        

        # 4. evaluate
        print("[4/5] Evaluating ...")
        y_prob = model.predict_proba(X_test)[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
        auc    = roc_auc_score(y_test, y_prob)
 
        cv = cross_val_score(
            xgb.XGBClassifier(**{k: v for k, v in params.items()
                                  if k not in ["early_stopping_rounds","eval_metric"]}),
            X, y, cv=StratifiedKFold(5), scoring="roc_auc"
        )
 
        mlflow.log_metric("auc",         round(float(auc), 4))
        mlflow.log_metric("cv_auc_mean", round(float(cv.mean()), 4))
        mlflow.log_metric("cv_auc_std",  round(float(cv.std()),  4))
 
        print(f"\n      AUC     : {auc:.4f}")
        print(f"      CV AUC  : {cv.mean():.4f} ± {cv.std():.4f}")
        print()
        print(classification_report(y_test, y_pred,
              target_names=["Active", "Churned"]))
        
        # Confusion matrix
        fig, ax = plt.subplots(figsize=(5, 4))
        ConfusionMatrixDisplay(
            confusion_matrix(y_test, y_pred),
            display_labels=["Active", "Churned"]
        ).plot(ax=ax, colorbar=False)
        ax.set_title("Churn — Confusion Matrix")
        plt.tight_layout()
        fig.savefig("docs/screenshots/churn_confusion_matrix.png", dpi=100)
        mlflow.log_artifact("docs/screenshots/churn_confusion_matrix.png")
        plt.close(fig)

        # SHAP summary
        print("      Computing SHAP values ...")
        explainer   = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)
        fig2, ax2   = plt.subplots(figsize=(8, 6))
        shap.summary_plot(shap_values, X_test, feature_names=FEATURE_COLS,
                          show=False, max_display=13)
        plt.tight_layout()
        fig2.savefig("docs/screenshots/churn_shap.png", dpi=100, bbox_inches="tight")
        mlflow.log_artifact("docs/screenshots/churn_shap.png")
        plt.close(fig2)
 
        mlflow.xgboost.log_model(model, "churn_model",
                                  registered_model_name="ecommerce_churn")
        
    # 5. Write predictions to PostgreSQL
    print("[5/5] Writing predictions to PostgreSQL ...")
    df["churn_probability"] = model.predict_proba(df[FEATURE_COLS])[:, 1]
    df["churn_label"] = pd.cut(
        df["churn_probability"],
        bins=[0.0, 0.33, 0.66, 1.0],
        labels=["Low", "Medium", "High"]
    ).astype(str)
 
    out = df[["customer_unique_id", "rfm_segment",
              "recency_days", 
               "frequency", "monetary",   
              "churn_probability", "churn_label"]].copy()
 
    out.to_sql("ml_churn_predictions", engine,
               if_exists="replace", index=False,
               method="multi", chunksize=1000)
 
    print(f"      {len(out):,} rows → ml_churn_predictions")
    print("\nDone. Open http://localhost:5000 to see MLflow logs.")
    return model
 
 
if __name__ == "__main__":
    train_churn_model()
 

