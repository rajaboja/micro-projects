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
function loadNext() { htmx.ajax('GET', '/next', '#now-playing'); }
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

app, rt = fast_app(live=True, hdrs=(Script(src="https://www.youtube.com/iframe_api"), yt_js,style))
def sim(a, b, quick=False):
    s = SequenceMatcher(None, a.lower(), b.lower())
    return s.quick_ratio() if quick else s.ratio()

def search_ytm(title, artists='', film='', k=1):
    primary_artist = artists.split(',')[0].strip()
    res = ytm.search(f'{title} {primary_artist}', filter='songs')[:10]
    if not res: return []
    match =[r for r in res if title.lower()==r.get('title','').lower()]
    if match:
        return match[:k]
    if artists:
        for r in res[:5]: r['_score'] = sim(artists, ','.join(a.get('name','') for a in r.get('artists',[])), quick=True)
        return sorted(res[:5], key=lambda r: r['_score'], reverse=True)[:k]
    return res[:k]

def get_yt_id(song):
    vid = song['id']
    if not vid:
        r = search_ytm(song.title, artists=song.artists, film=song.film)[0]
        vid = r['videoId']
        dur = r.get('duration_seconds')
        con.execute('UPDATE songs SET id=?, duration=? WHERE row_id=?', (vid, dur, int(song['row_id'])))
        con.commit()
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

@rt('/next')
def next():
    song = fetch_random()
    return SongInfo(song), Script(f"queueVideo('{song['id']}');")

@rt('/radio')
def get():
    return Titled("Crvn",
                    Grid(Div(id="player"),
                    Div(id="now-playing"),style="grid-template-columns: 1fr"))
                    
if os.environ.get("IN_SOLVEIT")=='True':
    server = JupyUvi(app)
else:
    serve(port=7000)

