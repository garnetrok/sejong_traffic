import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd

load_dotenv()

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
supabase = create_client(url, key)


def fetch_table_all(table_name: str) -> pd.DataFrame:
    all_rows = []
    page_size = 1000
    start = 0
    while True:
        resp = supabase.table(table_name).select("*").range(start, start + page_size - 1).execute()
        rows = resp.data
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        start += page_size
    return pd.DataFrame(all_rows)


if __name__ == "__main__":
    df = fetch_table_all("mock_accident_data")
    print("row count:", df.shape[0])
    print("columns:", df.columns.tolist())
    print(df.head(3))
