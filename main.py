from fastapi import FastAPI, Request, BackgroundTasks, Response, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
#from sqlalchemy import create_engine
import traceback
import sqlite3
import json
import requests
import os
import os
import openai
from textblob import TextBlob
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
from fastapi.responses import RedirectResponse
from typing import Optional


'''Core Functions'''
def get_user_playlists(username, sp):
    playlist_list = sp.user_playlists(username, limit=10)
    playlist_dict = {}
    for item in playlist_list['items']:
        playlist_dict[item['name'].strip()] = item['id'].strip()
    return playlist_dict


def get_playlist_tracks(username,playlist_id, sp):
    results = sp.user_playlist_tracks(username,playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    songs = []
    for track in tracks:
        songs.append(track['track']['name'])
    return songs


def get_object_songs(song_list):
    # #classifier = pipeline("zero-shot-classification", model = "./model")
    # classifier = pipeline("zero-shot-classification")
    # # candidate_labels = ["abstract", "concrete"]
    # candidate_labels = ["object", "idea"]
    #preds = classifier(song_list, candidate_labels)
    headers = {"Authorization": f"Bearer {os.environ['hg_api_token']}"}
    API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
    def query(payload):
        data = json.dumps(payload)
        response = requests.request("POST", API_URL, headers=headers, data=data)
        return json.loads(response.content.decode("utf-8"))
    data = query(
        {
            "inputs": song_list,
            "parameters": {"candidate_labels": ["object", "idea"]},
        }
    )
    object_songs = []
    iterator = 0
    for pred in data:
        if pred['labels'][0] == 'object':
            if pred['scores'][0] > .7:
                object_songs.append(song_list[iterator])
        iterator = iterator + 1
    return object_songs


def PPSongText(song_list):
    #song_list = ['First Class', 'Starting Over', 'Revival', "All Your'n", 'Rainbow', 'By and By', 'Astrovan', 'Strangers', 'You Should Probably Leave', 'Broken Halos', 'Heading South', 'Sedona', "Berry's Dream", 'The Fisherman', 'Colder Weather', 'Something in the Orange', 'Oklahoma Smokeshow', 'Heavy Eyes']
    text = '. '.join(song_list)
    tb = TextBlob(text)
    textPP = ', '.join(tb.noun_phrases)
    return textPP


def get_pics(items):
    prompt = f'pop art of A wimmelbilderbuch containing {items}'
    print(f'prompt: {prompt}')
    openai.api_key = os.environ["openai"]
    pics = openai.Image.create(prompt=prompt, n=1, size="512x512")
    urls = [item['url'] for item in pics['data']]
    return urls

def spotify_process(username,playlist):
    # init spotify
    client_id = os.environ['client_id']
    secret = os.environ['secret']
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=secret))

    # # mimic user inputs
    # username = 'the_captain_jack'
    # playlist = 'Chilly Morning'

    # playlsit retrieval
    playlists = get_user_playlists(username,sp)
    print('playlists done')

    # Song retrieval and Processing
    songs = get_playlist_tracks(username, playlists[playlist],sp)
    print('songs done')
    print(songs)
    object_songs = get_object_songs(songs)
    print('song classification done')
    print('object songs:')
    text = PPSongText(object_songs)
    print(text)

    # Image retrieval
    pics = get_pics(text)
    print(pics)

    # write to table
    df = pd.DataFrame([[f'user_{username}',pics[0],text]], columns=['username','url','keywords'])
    con = sqlite3.connect("temp.db")
    df.to_sql(name=f'user_{username}', con=con, if_exists='replace', index=False)
    return pics

''' APP Starts '''
# Launch app and mount assets
app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
templates = Jinja2Templates(directory="templates")
# init DB
con = sqlite3.connect("temp.db")


@app.get("/")
async def home(request: Request):
    try:
        return templates.TemplateResponse('index.html', {"request": request})

    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})

@app.post("/save_input")
async def save_input(request: Request, background_tasks: BackgroundTasks):
    try:
        # Collect User Input
        body = await request.body()
        print(body)
        out_list = []
        for x in body.decode('UTF-8').split('&')[:-1]:
            out_list.append(x.split('=')[1].replace('+', ' '))
        print(out_list)
        background_tasks.add_task(spotify_process, username=out_list[0], playlist=out_list[1])
        response = RedirectResponse(url="/loading")
        response.set_cookie("username", f'user_{out_list[0]}')
        return response

    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})

@app.post("/loading")
async def home(request: Request):
    try:
        return templates.TemplateResponse('loading.html', {"request": request})

    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})




@app.get("/final")
async def home(request: Request, username: Optional[bytes] = Cookie(None)):
    try:
        username = username.decode('UTF-8')
        sql = f'''select * from {username}'''
        df = pd.read_sql(sql, con=con)
        url = df.url.values[0]
        keywords = df.keywords[0]
        return templates.TemplateResponse('final.html', {"request": request, 'my_url':url, 'keywords':keywords})

    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})


if __name__ == '__main__':
    if os.environ['MODE'] == 'dev':
        import uvicorn
        uvicorn.run(app, port=4242, host='0.0.0.0')