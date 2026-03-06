import pandas as pd
fp = "micro-projects/carvaan/songlist.parquet"
df = pd.read_parquet(fp).drop_duplicates()
df.head()
import numpy as np

def test_continuity(df):
    mismatches = []
    for section, grp in df.groupby(['section','source']):
        expected = np.arange(1, len(grp)+1)
        actual = np.sort(grp['song_number'].values)
        if not np.array_equal(actual, expected):
            first_idx = int(np.argmax(actual != expected))
            mismatches.append((section, first_idx, expected[first_idx], actual[first_idx]))
    for section, idx, exp, act in mismatches:
        print(f"{section}: first mismatch at index {idx}, expected {exp}, got {act}")
    assert not mismatches, f"{len(mismatches)} mismatched group(s)"

test_continuity(df)
