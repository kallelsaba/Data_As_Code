import pandas as pd
for t in ["orders", "order_items", "customers"]:
    pd.read_csv(f"olist_{t}_dataset.csv").to_json(
        f"{t}.json", orient="records")
