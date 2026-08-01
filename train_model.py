import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from fetch_data import fetch_table_all
from prepare_features import build_monthly_features


def prepare_model_input(features_df: pd.DataFrame):
    df = features_df.copy()
    df = pd.get_dummies(df, columns=["legal_dong_name", "season"])
    feature_cols = [c for c in df.columns if c not in ["accident_count"]]
    X = df[feature_cols]
    y = df["accident_count"]
    return X, y, feature_cols


if __name__ == "__main__":
    acc_df = fetch_table_all("mock_accident_data")
    features_df = build_monthly_features(acc_df)

    X, y, feature_cols = prepare_model_input(features_df)

    train_mask = features_df["occurred_year"].isin([2024, 2025])
    test_mask = features_df["occurred_year"] == 2026

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    print(f"학습 데이터: {X_train.shape[0]}건, 검증 데이터: {X_test.shape[0]}건")

    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    print(f"\n평균 오차(MAE): {mae:.2f}건")

    importance = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\n중요 피처 Top 5:")
    print(importance.head(5))
