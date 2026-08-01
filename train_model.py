import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from fetch_data import fetch_table_all
from prepare_features import build_monthly_features


def prepare_model_input(features_df: pd.DataFrame):
    df = features_df.copy()
    df = pd.get_dummies(df, columns=["legal_dong_name", "season"])
    feature_cols = [c for c in df.columns if c not in ["accident_count"]]
    X = df[feature_cols]
    y = df["accident_count"]
    return X, y, feature_cols


def evaluate_model(features_df: pd.DataFrame) -> dict:
    """train/test 분리 후 평가지표 계산 (미래 예측용 모델과는 별개로, 성능 측정 전용)"""
    X, y, feature_cols = prepare_model_input(features_df)

    train_years = sorted(features_df["occurred_year"].unique())[:-1]  # 마지막 연도 빼고 학습
    test_year = sorted(features_df["occurred_year"].unique())[-1]     # 마지막 연도로 검증

    train_mask = features_df["occurred_year"].isin(train_years)
    test_mask = features_df["occurred_year"] == test_year

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred) ** 0.5
    r2 = r2_score(y_test, y_pred)

    return {
        "mae": round(float(mae), 3),
        "rmse": round(float(rmse), 3),
        "r2_score": round(float(r2), 3),
        "train_rows": int(X_train.shape[0]),
        "test_rows": int(X_test.shape[0]),
        "train_period": f"{min(train_years)}~{max(train_years)}",
        "test_period": str(test_year),
    }


if __name__ == "__main__":
    acc_df = fetch_table_all("mock_accident_data")
    features_df = build_monthly_features(acc_df)

    metrics = evaluate_model(features_df)
    print("평가 결과:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
