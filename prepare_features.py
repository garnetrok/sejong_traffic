import pandas as pd
from fetch_data import fetch_table_all


def month_to_season(m):
    if m in [12, 1, 2]:
        return "겨울"
    if m in [3, 4, 5]:
        return "봄"
    if m in [6, 7, 8]:
        return "여름"
    return "가을"


def build_monthly_features(acc_df: pd.DataFrame) -> pd.DataFrame:
    df = acc_df.copy()

    df["occurred_year"] = df["occurred_year"].fillna(0).astype(int)
    df["occurred_month"] = df["occurred_month"].fillna(0).astype(int)

    grouped = df.groupby(["legal_dong_name", "occurred_year", "occurred_month"]).agg(
        accident_count=("accident_id", "count"),
        fatalities=("fatalities", "sum"),
        serious_injuries=("serious_injuries", "sum"),
        night_ratio=("day_night", lambda x: (x == "야간").mean()),
        bad_weather_ratio=("weather", lambda x: x.isin(["비", "눈", "안개"]).mean()),
        icy_road_ratio=("road_surface", lambda x: x.isin(["결빙", "적설"]).mean()),
    ).reset_index()

    grouped["season"] = grouped["occurred_month"].apply(month_to_season)

    grouped = grouped.sort_values(["legal_dong_name", "occurred_year", "occurred_month"])
    grouped["past_3m_avg"] = (
        grouped.groupby("legal_dong_name")["accident_count"]
        .transform(lambda x: x.shift(1).rolling(window=3, min_periods=1).mean())
    )
    grouped["past_3m_avg"] = grouped["past_3m_avg"].fillna(grouped["accident_count"].mean())

    return grouped


if __name__ == "__main__":
    acc_df = fetch_table_all("mock_accident_data")
    features_df = build_monthly_features(acc_df)
    print("shape:", features_df.shape)
    print(features_df.head(10))
