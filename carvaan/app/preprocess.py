import pandas as pd
import sqlite3
import numpy as np
ignore_sections = [
    'BHAKTI', 'GURBANI', 'AYYAPPAN', 'GANESHA', 'HANUMAN', 'JESUS',
    'KANAKA DURGA', 'LORD KRISHNA', 'NARAYANA', 'RAMA', 'SAI BABA',
    'SHIVA', 'VENKATESWARA', 'SANSKRIT'
]

def create_songs_db(parquet_path='micro-projects/carvaan/songlist.parquet', db_path='library.db'):
    con = sqlite3.connect(db_path)
    df = (pd.read_parquet(parquet_path)
          .drop_duplicates(subset=('title', 'film', 'artists'))
          .reset_index(drop=True))
    print(f"Loaded {len(df)} unique songs from {parquet_path}")

    df = df[~df["section"].isin(ignore_sections)]
    df[["id", "duration"]] = None
    df['lang'] = np.where(df.source.str.contains('tamil'), 'ta', np.where(df.source.str.contains('telugu'), 'te', 'hi'))
    n = df.to_sql("songs", con=con, index_label="row_id",if_exists='replace')
    print(f"Wrote {n} rows to 'songs' table in {db_path}")

    con.close()
