from sqlalchemy import create_engine
import pandas as pd

DB_URI = "postgresql://dataops:dataops@postgres:5432/dataops"
engine = create_engine(DB_URI)

def query(sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, engine)
