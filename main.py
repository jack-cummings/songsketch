from fastapi import FastAPI, Request, BackgroundTasks, Response, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import time
from fastapi.responses import RedirectResponse
#from sqlalchemy import create_engine
import traceback
import sqlite3
import json
import requests
import os
import re
import openai
from textblob import TextBlob
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
from fastapi.responses import RedirectResponse
from typing import Optional
import random
import smtplib
from email.message import EmailMessage
import stripe
import starlette.status as status
import urllib.parse

'''Core Functions'''
def get_user_playlists(username, sp):
    playlist_list = sp.user_playlists(username, limit=10)
    playlist_dict = {}
    for item in playlist_list['items']:
        playlist_dict[item['name'].strip()] = item['id'].strip()
    return playlist_dict


def get_playlist_tracks(username,playlist_id, sp):
    results = sp.user_playlist_tracks(username,playlist_id, limit=50)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    songs = []
    for track in tracks:
        songs.append(track['track']['name'])
    songs_limit = songs[:50]
    return songs_limit

def get_playlist_tracks_url(url,sp):
    results = sp.playlist_tracks(url)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    songs = []
    for track in tracks:
        songs.append(track['track']['name'])
    songs_limit = songs[:50]
    return songs_limit


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
            "parameters": {"candidate_labels": ["object", "abstract"]},
        }
    )
    object_songs = []
    iterator = 0
    for pred in data:
        if pred['labels'][0] == 'object':
            #if pred['scores'][0] > .7:
            object_songs.append([song_list[iterator],pred['scores'][0]])
        iterator = iterator + 1
    df = pd.DataFrame(object_songs, columns = ['song','object_score']).sort_values('object_score', ascending=False)
    #head_len = int(round(df.shape[0]*.5,0))
    top_object_songs = df.head(5)['song'].to_list()
    return top_object_songs


def PPSongText(song_list):
    #song_list = ['First Class', 'Starting Over', 'Revival', "All Your'n", 'Rainbow', 'By and By', 'Astrovan', 'Strangers', 'You Should Probably Leave', 'Broken Halos', 'Heading South', 'Sedona', "Berry's Dream", 'The Fisherman', 'Colder Weather', 'Something in the Orange', 'Oklahoma Smokeshow', 'Heavy Eyes']
    song_list_mod = [re.sub(r'\(.*\)', '', x).replace('[remix]','').strip() for x in song_list]
    text = '. '.join(song_list_mod)
    # tb = TextBlob(text)
    # textPP = ', '.join(tb.noun_phrases)
    return text

def get_prompt(items,style):
    prompt = f'{style} of {items}'
    openai.api_key = os.environ["openai"]
    mod_raw = openai.Moderation.create(input=prompt)
    # custom prof check
    f = open("assets/profane_words.json", 'r')
    bad_words = json.load(f)
    bad_words_pattern = ' | '.join(bad_words)
    prompt = re.sub(bad_words_pattern,'',prompt)
    print(f'prompt: {prompt}')
    if mod_raw['results'][0]['flagged'] == False:
        return prompt
    else:
        return 'rejected'

def get_pics(prompt):
    #pics = openai.Image.create(prompt=prompt, n=3, size="256x256")
    pics = openai.Image.create(prompt=prompt, n=5, size="1024x1024")
    urls = [item['url'] for item in pics['data']]
    return urls

def spotify_process(playlist_id,uniqueID, style):
    try:
        # init spotify
        client_id = os.environ['client_id']
        secret = os.environ['secret']
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=secret))

        # url song retrieval
        songs = get_playlist_tracks_url(playlist_id,sp)
        print('songs done')
        print(songs)
        object_songs = get_object_songs(songs)
        print('song classification done')
        print('object songs:')
        text = PPSongText(object_songs)
        print(text)

        prompt = get_prompt(text,style)
    except:
        # write to table
        df = pd.DataFrame([[uniqueID, 'error', 'error']], columns=['uniqueID', 'prompt', 'keywords'])
        con = sqlite3.connect("temp.db")
        df.to_sql(name=uniqueID, con=con, if_exists='replace', index=False)
        return prompt


    # write to table
    df = pd.DataFrame([[uniqueID,prompt,text]], columns=['uniqueID','prompt','keywords'])
    con = sqlite3.connect("temp.db")
    df.to_sql(name=uniqueID, con=con, if_exists='replace', index=False)
    return prompt

def sendEmail(pics,status):
    email_address = "johnmcummings3@gmail.com"
    email_password = os.environ['email_code']

    # create email
    msg = EmailMessage()
    msg['Subject'] = f"Song Sketch Log - {status}"
    msg['From'] = email_address
    msg['To'] = email_address
    if status == 'good':
        msg.set_content(f"Someone completed a song sketch! \n pics: {pics}")
    else:
        msg.set_content(f"Error song sketch! \n msg: {pics}")

    # send email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(email_address, email_password)
        smtp.send_message(msg)

def setBasePath(mode):
    if mode.lower() == 'dev':
        basepath = 'http://0.0.0.0:4242'
    elif mode.lower() == 'prod':
        basepath = 'https://songsketch.herokuapp.com'
    return basepath

''' APP Starts '''
# Launch app and mount assets
app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
templates = Jinja2Templates(directory="templates")
# init DB
con = sqlite3.connect("temp.db")
basepath = setBasePath(os.environ['MODE'])
stripe.api_key = os.environ['STRIPE_KEY_PROD']

@app.get("/")
async def home(request: Request):
    try:
        return templates.TemplateResponse('index_v3.html', {"request": request})

    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})

@app.get("/pricing")
async def home(request: Request):
    try:
        return templates.TemplateResponse('pricing.html', {"request": request})

    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})

@app.get("/contact")
async def home(request: Request):
    try:
        return templates.TemplateResponse('contact.html', {"request": request})

    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})

@app.get("/about")
async def home(request: Request):
    try:
        return templates.TemplateResponse('about.html', {"request": request})

    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})

@app.get("/playlist_not_found")
async def home(request: Request):
    try:
        return templates.TemplateResponse('no_pl.html', {"request": request})

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

        # check if playlist accessible
        try:
            playlist_id = out_list[0].split('playlist%2F')[1].split('%3F')[0]
            #playlist_id = out_list[0].split('playlist')[1].split('%')[1][2:]
            client_id = os.environ['client_id']
            secret = os.environ['secret']
            sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=secret))
            sp.playlist_tracks(playlist_id)
            pl_access = True
        except:
            pl_access = False
        # Direct to either next step or cusotom error based on PL access
        if pl_access:
            # if PL access, kick off processing
            uniqueID = f'uid{random.randint(0, 100000)}'
            background_tasks.add_task(spotify_process, playlist_id=playlist_id, style=out_list[1], uniqueID=uniqueID)
            if out_list[-1] in os.environ['promocodes'].split(','):
                response = RedirectResponse(url="/loading", status_code=status.HTTP_302_FOUND)
                response.set_cookie("uniqueID", uniqueID)
            else:
                # response = RedirectResponse(url="/checkout", status_code=status.HTTP_302_FOUND)
                # response.set_cookie("uniqueID", uniqueID)
                # # free Mode
                response = RedirectResponse(url="/loading", status_code=status.HTTP_302_FOUND)
                response.set_cookie("uniqueID", uniqueID)
        else:
            # if not- pl not found error
            response = RedirectResponse(url='/playlist_not_found', status_code=status.HTTP_302_FOUND)


        return response

    except Exception as e:
        print(e)
        background_tasks.add_task(sendEmail, pics=e, status='error')
        return templates.TemplateResponse('error.html', {"request": request})

@app.get("/checkout")
async def checkout_5(request: Request):
    try:
        checkout_session = stripe.checkout.Session.create(
            success_url=basepath + "/loading?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=basepath,
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price": os.environ['price'],
                "quantity": 1
            }],
            )
        return RedirectResponse(checkout_session.url, status_code=303)

    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})

@app.get("/loading")
async def home(request: Request,background_tasks: BackgroundTasks, uniqueID: Optional[bytes] = Cookie(None)):
    try:
        time.sleep(5)
        uniqueID = uniqueID.decode('UTF-8')
        sql = f'''select * from {uniqueID}'''
        df = pd.read_sql(sql, con=con)
        if df['prompt'].values[0] != 'error':
            #return templates.TemplateResponse('art_ready.html', {"request": request})
            response = RedirectResponse(url='/final', status_code=status.HTTP_302_FOUND)
            return response
        else:
            try:
                background_tasks.add_task(sendEmail, pics='error in loading flow', status='error')
                return templates.TemplateResponse('error.html', {"request": request})
            except Exception as e:
                print(e)
                return templates.TemplateResponse('loading.html', {"request": request})

    except Exception as e:
        print(e)
        background_tasks.add_task(sendEmail, pics="prompt wasn't ready, kicking to loading, if no good in a few minutes treat as error", status='error')
        return templates.TemplateResponse('loading.html', {"request": request})


@app.get("/final")
async def home(request: Request, background_tasks: BackgroundTasks, uniqueID: Optional[bytes] = Cookie(None)):
    try:
        uniqueID = uniqueID.decode('UTF-8')
        sql = f'''select * from {uniqueID}'''
        df = pd.read_sql(sql, con=con)
        prompt = df.prompt.values[0]
        keywords = df.keywords[0]

        # Image retrieval
        if prompt != 'rejected':
            pics = get_pics(prompt)
            print(pics)
            background_tasks.add_task(sendEmail, pics=pics, status='good')
            return templates.TemplateResponse('final_gallery.html', {"request": request, 'url_1': pics[0],
                                                             'url_2': pics[1], 'url_3': pics[2],
                                                            'url_4': pics[3], 'url_5': pics[4],
                                                            'keywords': keywords})
        else:
            return templates.TemplateResponse('rejected.html', {"request": request, 'keywords': keywords})

    except Exception as e:
        print(e)
        background_tasks.add_task(sendEmail, pics=e, status='error')
        return templates.TemplateResponse('error.html', {"request": request})


if __name__ == '__main__':
    if os.environ['MODE'] == 'dev':
        import uvicorn
        uvicorn.run(app, port=4242, host='0.0.0.0')