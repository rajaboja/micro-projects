import os
import sqlite3
import pandas as pd
from difflib import SequenceMatcher
from ytmusicapi import YTMusic

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'library.db')
ytm = YTMusic()
con = sqlite3.connect(DB_PATH, check_same_thread=False)

def get_unmatched_films(limit=10):
    return pd.read_sql(
        "SELECT film, COUNT(*) as unmatched FROM songs WHERE (id IS NULL OR id='') GROUP BY film ORDER BY unmatched DESC LIMIT ?",
        con, params=[limit])

def search_album(film):
    results = ytm.search(f'{film} soundtrack', filter='albums')[:8]
    return [{'title': r.get('title'), 'year': r.get('year'), 'browseId': r.get('browseId'),
             'artists': ', '.join(a['name'] for a in r.get('artists', []))} for r in results]

def get_album_tracks(film, album_browse_id):
    album = ytm.get_album(album_browse_id)
    tracks = [{'#': i+1, 'title': t['title'], 'videoId': t.get('videoId'), 'duration_seconds': t.get('duration_seconds')}
              for i, t in enumerate(album.get('tracks', []))]
    db_songs = pd.read_sql(
        "SELECT row_id, title FROM songs WHERE film=? AND (id IS NULL OR id='') ORDER BY title",
        con, params=[film])
    return {'album_tracks': tracks, 'unmatched_db_songs': db_songs.to_dict('records')}

def batch_assign_ids(assignments):
    try:
        for row_id, video_id, duration_seconds in assignments:
            con.execute('UPDATE songs SET id=?, duration=? WHERE row_id=?', (video_id, duration_seconds, int(row_id)))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return f'{len(assignments)} songs updated'

def get_unmatched_songs(limit=10):
    return pd.read_sql(
        "SELECT row_id, title, film, artists FROM songs WHERE (id IS NULL OR id='') LIMIT ?",
        con, params=[limit])

def _sim(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def search_song(title, artists='', film=''):
    primary_artist = artists.split(',')[0].strip() if artists else ''
    res = ytm.search(f'{title} {primary_artist}'.strip(), filter='songs')[:10]
    if not res: return []
    exact = [r for r in res if title.lower() == r.get('title', '').lower()]
    if exact:
        if film:
            film_match = [r for r in exact if film.lower() == r.get('album', {}).get('name', '').lower()]
            if film_match: exact = film_match
        candidates = exact
    elif artists:
        for r in res[:5]: r['_score'] = _sim(artists, ', '.join(a['name'] for a in r.get('artists', [])))
        candidates = sorted(res[:5], key=lambda r: r['_score'], reverse=True)
    else:
        candidates = res
    return [{'title': r['title'], 'videoId': r.get('videoId'), 'duration_seconds': r.get('duration_seconds'),
             'album': r.get('album', {}).get('name', ''), 'artists': ', '.join(a['name'] for a in r.get('artists', []))}
            for r in candidates[:5]]
