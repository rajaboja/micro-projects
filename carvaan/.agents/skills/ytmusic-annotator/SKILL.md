---
name: ytmusic-annotator
description: Finds YouTube Music track IDs from song metadata and updates a SQLite database. Use when annotating or enriching a music library with YouTube Music IDs.
compatibility: Requires Python 3, ytmusicapi, pandas, sqlite3
---

## Database schema

Songs are stored in a SQLite table `songs` with columns: `row_id`, `title`, `artists`, `film`, `lang`, `id` (YouTube Music video ID), `duration` (seconds).

## Workflow

Start by matching songs at the album level. Use `get_films()` to retrieve films with unannotated songs. For each film, use `get_songs(film)` to get the unmatched songs, then `search_album(film)` to find the soundtrack on YouTube Music. Pick the best album match and fetch its tracks with `get_album_tracks(browseId)`. Match DB songs to album tracks and call `assign_id` for each match.

For songs still unmatched after the album pass, fall back to per-song search. Use `get_songs()` to find remaining songs, then `search_song(title, artists, film)` for each, and call `assign_id` for the best match.

## Guidelines

- Titles may have minor spelling variations — use judgement to match
- Skip remixes, covers, and compilations
- If no good match is found, skip and move on
- Collect all matches first, then call `assign_id` in bulk rather than one at a time

## Tools

```python
import pandas as pd
import sqlite3
from ytmusicapi import YTMusic

ytm = YTMusic()
con = sqlite3.connect('library.db', check_same_thread=False)

def get_films(limit=10):
    "List films that have songs without YouTube IDs, with count per film."
    df = pd.read_sql("SELECT film, COUNT(*) as unmatched_count FROM songs WHERE (id IS NULL OR id='') AND film != '' GROUP BY film ORDER BY unmatched_count DESC LIMIT ?", con, params=[limit])
    if df.empty: return []
    return df.to_dict(orient='records')

def get_songs(film=None, limit=10):
    "Get songs without a YouTube ID. Optionally filter by film."
    if film:
        df = pd.read_sql("SELECT row_id, title, artists FROM songs WHERE film=? AND (id IS NULL OR id='') ORDER BY title", con, params=[film])
    else:
        df = pd.read_sql("SELECT row_id, title, artists, film FROM songs WHERE (id IS NULL OR id='') ORDER BY film, title LIMIT ?", con, params=[limit])
    if df.empty: return []
    return df.to_dict(orient='records')

def search_album(film):
    "Search YTMusic for an album/film soundtrack. Returns top album results."
    res = ytm.search(film, filter='albums')[:5]
    if not res: return []
    return [dict(idx=i, title=r.get('title',''), artists=', '.join(a.get('name','') for a in r.get('artists',[])), browseId=r.get('browseId',''), year=r.get('year','')) for i,r in enumerate(res)]

def get_album_tracks(album_browse_id):
    "Fetch all tracks from a YouTube Music album."
    album = ytm.get_album(album_browse_id)
    return [dict(title=t.get('title',''), videoId=t.get('videoId',''), duration_seconds=t.get('duration_seconds','')) for t in album.get('tracks', [])]

def search_song(title, artists='', film=''):
    "Search YouTube Music for a song and return top results."
    query = f'{title} {artists.split(",")[0].strip()}'.strip()
    res = ytm.search(query, filter='songs')[:5]
    if not res: return []
    return [dict(idx=i, title=r.get('title',''), artists=', '.join(a.get('name','') for a in r.get('artists',[])), album=r.get('album',{}).get('name',''), videoId=r.get('videoId',''), duration_seconds=r.get('duration_seconds','')) for i,r in enumerate(res)]

def assign_id(row_id, video_id, duration_seconds):
    "Assign a YouTube ID and duration to a song by row_id."
    con.execute('UPDATE songs SET id=?, duration=? WHERE row_id=?', (video_id, duration_seconds, int(row_id)))
    con.commit()
    return f"Updated row {row_id}."
```
