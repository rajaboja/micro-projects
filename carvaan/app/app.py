import pandas as pd
import sqlite3
from fasthtml.common import *
from fasthtml.jupyter import JupyUvi
from difflib import SequenceMatcher
from ytmusicapi import YTMusic
import os

ytm = YTMusic()
con = sqlite3.connect('library.db', check_same_thread=False)

yt_js = Script("""
var player, vids = [];
function loadNext() { htmx.ajax('GET', '/nxt', '#now-playing'); }
function onYouTubeIframeAPIReady() {
    player = new YT.Player('player', {
        playerVars: { enablejsapi: 1, color: 'white' },
        events: {
            'onReady': loadNext,
            'onStateChange': function(e) {
                if (e.data === YT.PlayerState.ENDED && player.getPlaylistIndex() >= vids.length - 1)
                    loadNext();
            }
        }
    });
}
function queueVideo(vid) {
    vids.push(vid);
    player.loadPlaylist(vids, vids.length - 1);
}
""")

style = Style("""
#player { filter: grayscale(100%); aspect-ratio: 1/1; max-width: 360px; width: 100%; }
""")

app, rt = fast_app(hdrs=(Script(src="https://www.youtube.com/iframe_api"), yt_js,style))
def sim(a, b, quick=False):
    s = SequenceMatcher(None, a.lower(), b.lower())
    return s.quick_ratio() if quick else s.ratio()

def search_ytm(title, artists='', film='', k=1):
    primary_artist = artists.split(',')[0].strip()
    res = ytm.search(f'{title} {primary_artist}', filter='songs')[:10]
    if not res: return []
    match =[r for r in res if title.lower()==r.get('title','').lower()]
    if match:
        if film:
            film_match = [r for r in match if film.lower() == r.get('album',{}).get('name','').lower()]
            if film_match: return film_match[:k]
        return match[:k]
    if artists:
        for r in res[:5]: r['_score'] = sim(artists, ','.join(a.get('name','') for a in r.get('artists',[])), quick=True)
        return sorted(res[:5], key=lambda r: r['_score'], reverse=True)[:k]
    return res[:k]

async def update_album_ids(film, album_browse_id):
    album = ytm.get_album(album_browse_id)
    tracks = {t.get('title','').lower(): t for t in album.get('tracks', [])}
    db_songs = pd.read_sql(
        "SELECT row_id, title FROM songs WHERE film=? AND (id IS NULL OR id='') ORDER BY title",
        con, params=[film])
    db_titles = {r['title'].lower(): r for _, r in db_songs.iterrows()}

    for title in db_titles.keys() & tracks.keys():
        _update_song(db_titles[title]['row_id'], tracks[title])

    unmatched_tracks = set(tracks.keys() - db_titles.keys())
    for db_t in db_titles.keys() - tracks.keys():
        if not unmatched_tracks: break
        best = max(unmatched_tracks, key=lambda t: sim(db_t, t))
        if sim(db_t, best) >= 0.9:
            _update_song(db_titles[db_t]['row_id'], tracks[best])
            unmatched_tracks.discard(best)

    con.commit()


def _update_song(row_id, track):
    vid, dur = track.get('videoId'), track.get('duration_seconds')
    if vid: con.execute('UPDATE songs SET id=?, duration=? WHERE row_id=?', (vid, dur, int(row_id)))

def get_yt_id(song):
    vid = song['id']
    if not vid:
        r = search_ytm(song.title, artists=song.artists, film=song.film)[0]
        vid = r.get('videoId')
        _update_song(song['row_id'], r)
        con.commit()
        album_info = r.get('album', {})
        if song.film and album_info.get('name','').lower() == song.film.lower() and album_info.get('id'):
            bg_task(update_album_ids(song.film, album_info['id']))
    return vid

def fetch_random():
    song = pd.read_sql("SELECT * FROM songs ORDER BY RANDOM() LIMIT 1", con=con).iloc[0]
    song["id"] = get_yt_id(song)
    return song

def SongInfo(song):
    return Div(
        P(Strong("Title: "), song['title']),
        P(Strong("Album: "), song['film']),
        P(Strong("Artists: "), song['artists']))

@rt
async def nxt():
    song = fetch_random()
    return SongInfo(song), Script(f"queueVideo('{song['id']}');")
@rt
def radio():
    return Titled("Crvn",Div(id="player"),Div(id="now-playing"))
if os.environ.get("IN_SOLVEIT")=='True':
    server = JupyUvi(app)
else:
    serve(port=7000)
