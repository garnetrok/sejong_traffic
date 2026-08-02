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
    """train/validation/test 3단 분할.
    - train+validation: 하이퍼파라미터 후보 비교용
    - test: 가장 최근 연도, 최종 확인 전용 (한 번만 사용)
    """
    years = sorted(features_df["occurred_year"].unique())

    if len(years) < 3:
        raise ValueError("3단 분할하려면 최소 3개 연도 데이터가 필요함")

    train_years = years[:-2]
    val_year = years[-2]
    test_year = years[-1]

    X, y, feature_cols = prepare_model_input(features_df)

    train_mask = features_df["occurred_year"].isin(train_years)
    val_mask = features_df["occurred_year"] == val_year
    test_mask = features_df["occurred_year"] == test_year

    X_train, y_train = X[train_mask], y[train_mask]
    X_val, y_val = X[val_mask], y[val_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    # 1) validation으로 하이퍼파라미터 후보 비교
    candidates = [
        {"n_estimators": 100, "max_depth": 4},
        {"n_estimators": 200, "max_depth": 6},
        {"n_estimators": 300, "max_depth": 8},
    ]

    best_params = None
    best_val_mae = float("inf")
    for params in candidates:
        m = RandomForestRegressor(random_state=42, **params)
        m.fit(X_train, y_train)
        val_pred = m.predict(X_val)
        val_mae = mean_absolute_error(y_val, val_pred)
        if val_mae < best_val_mae:
            best_val_mae = val_mae
            best_params = params

    # 2) 가장 좋았던 설정으로 train+val 합쳐서 재학습
    X_trainval = pd.concat([X_train, X_val])
    y_trainval = pd.concat([y_train, y_val])
    final_model = RandomForestRegressor(random_state=42, **best_params)
    final_model.fit(X_trainval, y_trainval)

    # 3) test로 최종 확인 (한 번만)
    y_pred = final_model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred) ** 0.5
    r2 = r2_score(y_test, y_pred)

    return {
        "mae": round(float(mae), 3),
        "rmse": round(float(rmse), 3),
        "r2_score": round(float(r2), 3),
        "val_mae": round(float(best_val_mae), 3),
        "best_params": str(best_params),
        "train_rows": int(X_trainval.shape[0]),
        "test_rows": int(X_test.shape[0]),
        "train_period": f"{min(train_years)}~{val_year}",
        "test_period": str(test_year),
    }


if __name__ == "__main__":
    acc_df = fetch_table_all("mock_accident_data")
    features_df = build_monthly_features(acc_df)

    metrics = evaluate_model(features_df)
    print("평가 결과 (train/validation/test 3단 분할):")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
