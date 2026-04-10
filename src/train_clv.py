"""
LightGBM Customer Lifetime Value regression model.
Logs metrics and artifacts to MLflow.
Writes CLV predictions to PostgreSQL (ml_clv_predictions table).
"""

import os 
import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.lightgbm
import lightgbm as lgb
import shap
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
 
from src.features import build_feature_matrix, get_rfm_segments, CLV_TARGET
from src.db import engine

load_dotenv()
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment("ecommerce-clv-prediction")

CLV_FEATURES = [
    "recency_days", "frequency",
    "avg_order_value", "max_order_value", "min_order_value", "std_order_value",
    "review_count", "avg_review_score",
    "unique_categories", "customer_age_days", "orders_per_month",
]

def train_clv_model():
    """Complete CLV training pipeline. Returns trained LightGBM model."""
 

    print("CLV MODEL TRAINING")
 
    #  1. Data 
    print("\n[1/4] Building feature matrix ...")
    df = build_feature_matrix()
    df = get_rfm_segments(df)
 
    # Log-transform monetary value: fixes right-skew, improves model fit
    df["log_monetary"] = np.log1p(df[CLV_TARGET])
 
    X = df[CLV_FEATURES]
    y = df["log_monetary"]
 
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
 
    print(f"      {len(X):,} customers | "
          f"monetary mean R${df[CLV_TARGET].mean():.2f}")
    

    #  2. Train LightGBM 
    print("[2/4] Training LightGBM ...")
    params = {
        "n_estimators":      600,
        "max_depth":         6,
        "learning_rate":     0.03,
        "num_leaves":        63,
        "subsample":         0.8,
        "colsample_bytree":  0.8,
        "reg_alpha":         0.1,
        "reg_lambda":        1.0,
        "min_child_samples": 20,
        "random_state":      42,
    }
 
    with mlflow.start_run(run_name="lightgbm-clv-v1"):
        mlflow.log_params(params)
        mlflow.log_param("target_transform", "log1p")
 
        model = lgb.LGBMRegressor(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[
                lgb.early_stopping(50, verbose=False),
                lgb.log_evaluation(0),
            ]
        )

        #  3. Evaluate (back in R$) 
        print("[3/4] Evaluating ...")
        preds   = np.expm1(model.predict(X_test)).clip(min=0)
        actuals = np.expm1(y_test.values)
 
        mae  = mean_absolute_error(actuals, preds)
        rmse = np.sqrt(mean_squared_error(actuals, preds))
        r2   = r2_score(actuals, preds)
        mape = float(np.mean(np.abs((actuals - preds)
                                    / np.maximum(actuals, 1))) * 100)
 
        mlflow.log_metrics({
            "mae":  round(mae,  2),
            "rmse": round(rmse, 2),
            "r2":   round(r2,   4),
            "mape": round(mape, 2),
        })
        print(f"      MAE  : R${mae:.2f}")
        print(f"      RMSE : R${rmse:.2f}")
        print(f"      R²   : {r2:.4f}")
        print(f"      MAPE : {mape:.2f}%")
 
        # Scatter plot
        sample = np.random.choice(len(actuals), min(2000, len(actuals)), replace=False)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.scatter(actuals[sample], preds[sample], alpha=0.3, s=10, color="#378ADD")
        mv = max(actuals.max(), preds.max())
        ax.plot([0, mv], [0, mv], "r--", lw=1, label="Perfect")
        ax.set_xlabel("Actual CLV (R$)")
        ax.set_ylabel("Predicted CLV (R$)")
        ax.set_title(f"CLV Prediction  R²={r2:.3f}")
        ax.legend()
        plt.tight_layout()
        fig.savefig("docs/screenshots/clv_scatter.png", dpi=100)
        mlflow.log_artifact("docs/screenshots/clv_scatter.png")
        plt.close(fig)
 
        # SHAP
        print("      Computing SHAP values ...")
        explainer   = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)
        fig2, ax2   = plt.subplots(figsize=(8, 6))
        shap.summary_plot(shap_values, X_test, feature_names=CLV_FEATURES,
                          show=False, max_display=11)
        plt.tight_layout()
        fig2.savefig("docs/screenshots/clv_shap.png", dpi=100, bbox_inches="tight")
        mlflow.log_artifact("docs/screenshots/clv_shap.png")
        plt.close(fig2)
 
        mlflow.lightgbm.log_model(model, "clv_model",
                                   registered_model_name="ecommerce_clv")
        

    #  4. Write predictions to PostgreSQL 
    print("[4/4] Writing predictions to PostgreSQL ...")
    df["predicted_clv"] = np.expm1(model.predict(df[CLV_FEATURES])).clip(min=0).round(2)
    df["clv_segment"]   = pd.qcut(
        df["predicted_clv"], q=4,
        labels=["Bronze", "Silver", "Gold", "Platinum"]
    ).astype(str)
 
    out = df[["customer_unique_id", "rfm_segment",
              "monetary", "predicted_clv", "clv_segment",
              "recency_days", "frequency"]].copy()
 
    out.to_sql("ml_clv_predictions", engine,
               if_exists="replace", index=False,
               method="multi", chunksize=1000)
 
    print(f"      {len(out):,} rows → ml_clv_predictions")
    print("\nDone. Open http://localhost:5000 to see MLflow logs.")
    return model
 
 
if __name__ == "__main__":
    train_clv_model()