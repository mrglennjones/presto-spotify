# presto-spotify
display your Spotify 'now playing' song along with the cover image, time elapsed and progress bar

![1000021093](https://github.com/user-attachments/assets/833cc663-48a5-45fb-b680-1c58ec532126)


### this is very beta and just a proof of concept

## guide
- goto https://developer.spotify.com/dashboard and create an app, your api info will be available there to copy to your secrets.py
- create secrets.py with:-
```
WIFI_SSID = ""
WIFI_PASSWORD = ""

# Spotify credentials
CLIENT_ID = ''
CLIENT_SECRET = ''
REDIRECT_URI = ''
ACCESS_TOKEN = ''
```
- insert an sd card, the cover images and token json file is saved there.
- on initilisation the app will ask for your token which lasts for 1hr then needs to be refreshed.
- Visit the link provided in thonny then copy/paste the code found in your browser address bar: https://open.spotify.com/?code=''
