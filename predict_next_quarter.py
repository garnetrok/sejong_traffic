import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from fetch_data import fetch_table_all
from prepare_features import build_monthly_features, month_to_season
from train_model import prepare_model_input


def get_next_quarter_months(latest_year, latest_month):
    months = []
    y, m = int(latest_year), int(latest_month)
    for _ in range(3):
        m += 1
        if m > 12:
            m = 1
            y += 1
        months.append((y, m))
    return months


def build_future_rows(features_df: pd.DataFrame, target_months: list) -> pd.DataFrame:
    rows = []
    for dong in features_df["legal_dong_name"].unique():
        dong_history = features_df[features_df["legal_dong_name"] == dong].sort_values(
            ["occurred_year", "occurred_month"]
        )
        recent_avg = dong_history["accident_count"].tail(3).mean()
        recent_night_ratio = dong_history["night_ratio"].tail(3).mean()
        recent_bad_weather = dong_history["bad_weather_ratio"].tail(3).mean()
        recent_icy_ratio = dong_history["icy_road_ratio"].tail(3).mean()
        recent_fatalities = dong_history["fatalities"].tail(3).mean()
        recent_serious = dong_history["serious_injuries"].tail(3).mean()

        for (y, m) in target_months:
            rows.append({
                "legal_dong_name": dong,
                "occurred_year": y,
                "occurred_month": m,
                "season": month_to_season(m),
                "night_ratio": recent_night_ratio,
                "bad_weather_ratio": recent_bad_weather,
                "icy_road_ratio": recent_icy_ratio,
                "fatalities": recent_fatalities,
                "serious_injuries": recent_serious,
                "past_3m_avg": recent_avg,
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    acc_df = fetch_table_all("mock_accident_data")
    features_df = build_monthly_features(acc_df)

    X_all, y_all, feature_cols = prepare_model_input(features_df)
    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    model.fit(X_all, y_all)

    latest_year = features_df["occurred_year"].max()
    latest_month = features_df[features_df["occurred_year"] == latest_year]["occurred_month"].max()
    target_months = get_next_quarter_months(latest_year, latest_month)
    print(f"가장 최근 데이터: {latest_year}년 {latest_month}월")
    print(f"예측 대상: {target_months}")

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

    print("\n다음 분기 예상 위험지역 Top 5:")
    print(quarter_summary.head(5))
