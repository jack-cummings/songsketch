from textblob import TextBlob
import spotipy
import os
from spotipy.oauth2 import SpotifyClientCredentials
from transformers import pipeline

def get_user_playlists(username):
    playlist_list = sp.user_playlists(username, limit=10)
    playlist_dict = {}
    for item in playlist_list['items']:
        playlist_dict[item['name'].strip()] = item['id'].strip()
    return playlist_dict

def get_playlist_tracks(username,playlist_id):
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
    classifier = pipeline("zero-shot-classification")
    # candidate_labels = ["abstract", "concrete"]
    candidate_labels = ["object", "idea"]
    preds = classifier(song_list, candidate_labels)
    object_songs = []
    iterator = 0
    for pred in preds:
        if pred['labels'][0] == 'object':
            object_songs.append(song_list[iterator])
        iterator = iterator + 1
    return object_songs

def PPSongText(song_list):
    #song_list = ['First Class', 'Starting Over', 'Revival', "All Your'n", 'Rainbow', 'By and By', 'Astrovan', 'Strangers', 'You Should Probably Leave', 'Broken Halos', 'Heading South', 'Sedona', "Berry's Dream", 'The Fisherman', 'Colder Weather', 'Something in the Orange', 'Oklahoma Smokeshow', 'Heavy Eyes']
    text = '. '.join(song_list)
    tb = TextBlob(text)
    textPP = ', '.join(tb.noun_phrases)
    return textPP

# init spotify
client_id = os.environ['client_id']
secret = os.environ['secret']
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=secret))

# mimic user inputs
username = 'the_captain_jack'
playlist = 'Chilly Morning'

# playlsit retrieval
playlists = get_user_playlists(username)
print('playlists done')

# Song retrieval and Processing
songs = get_playlist_tracks(username, playlists[playlist])
print('songs done')
object_songs = get_object_songs(songs)
print('song classification done')
print('object songs')
text = PPSongText(object_songs)

print(text)


# pop art of A wimmelbilderbuch containing a rainbow, a astrovan,  sedona,  fisherman, eyes


