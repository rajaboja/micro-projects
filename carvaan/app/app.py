import pandas as pd
import sqlite3
from fasthtml.common import *
from fasthtml.jupyter import JupyUvi
import os

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
            },
            'onError': loadNext
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
def fetch_random():
    song = pd.read_sql("SELECT * FROM songs ORDER BY RANDOM() LIMIT 1", con=con).iloc[0]
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
