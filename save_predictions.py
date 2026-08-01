import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from fetch_data import fetch_table_all
from prepare_features import build_monthly_features
from train_model import prepare_model_input, evaluate_model
from predict_next_quarter import get_next_quarter_months, build_future_rows

load_dotenv()
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
supabase = create_client(url, key)


def run_and_save():
    acc_df = fetch_table_all("mock_accident_data")
    features_df = build_monthly_features(acc_df)

    # 1) 평가 먼저 수행 (학습에 안 쓴 데이터로 성능 측정)
    eval_metrics = evaluate_model(features_df)
    eval_metrics["model_version"] = "rf_v1"

    supabase.table("ml_model_eval").insert(eval_metrics).execute()
    print(f"평가지표 저장 완료: MAE={eval_metrics['mae']}, R2={eval_metrics['r2_score']}")

    # 2) 실전 예측용 모델은 전체 데이터로 재학습 (다음 분기 예측이 목적이므로)
    X_all, y_all, feature_cols = prepare_model_input(features_df)
    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    model.fit(X_all, y_all)

    latest_year = features_df["occurred_year"].max()
    latest_month = features_df[features_df["occurred_year"] == latest_year]["occurred_month"].max()
    target_months = get_next_quarter_months(latest_year, latest_month)

    future_df = build_future_rows(features_df, target_months)
    future_encoded = pd.get_dummies(future_df, columns=["legal_dong_name", "season"])
    future_encoded = future_encoded.reindex(columns=feature_cols, fill_value=0)

    predictions = model.predict(future_encoded)
    future_df["predicted_accident_count"] = predictions.round(1)

    quarter_summary = (
        future_df.groupby("legal_dong_name")["predicted_accident_count"]
        .sum()
        .round(1)
        .sort_values(ascending=False)
        .reset_index()
    )
    quarter_summary.columns = ["legal_dong_name", "predicted_quarter_accidents"]
    quarter_summary["risk_rank"] = range(1, len(quarter_summary) + 1)

    period_label = f"{target_months[0][0]}-{target_months[0][1]:02d} ~ {target_months[-1][0]}-{target_months[-1][1]:02d}"
    quarter_summary["target_period"] = period_label

    records = quarter_summary.to_dict(orient="records")
    supabase.table("ml_safety_scores").upsert(records, on_conflict="legal_dong_name").execute()

    print(f"예측 저장 완료: {len(records)}개 동, 대상 기간 {period_label}")

    return {"predictions": records, "eval": eval_metrics}


if __name__ == "__main__":
    run_and_save()
