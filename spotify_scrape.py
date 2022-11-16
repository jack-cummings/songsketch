from textblob import TextBlob
import spotipy
import os
from spotipy.oauth2 import SpotifyClientCredentials

client_id = os.environ['client_id']
secret = os.environ['secret']

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=client_id,
                                                           client_secret=secret))

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

songs = get_playlist_tracks('the_captain_jack','3TQ8O9vpTSqdSC36ZxBqHS')
#songs = ['First Class', 'Starting Over', 'Revival', "All Your'n", 'Rainbow', 'By and By', 'Astrovan', 'Strangers', 'You Should Probably Leave', 'Broken Halos', 'Heading South', 'Sedona', "Berry's Dream", 'The Fisherman', 'Colder Weather', 'Something in the Orange', 'Oklahoma Smokeshow', 'Heavy Eyes']
text = '. '.join(songs)
tb = TextBlob(text)
textPP= ', '.join(tb.noun_phrases)
print(textPP)

#print(songs)