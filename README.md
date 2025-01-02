# presto-spotify
display your now Spotify playing song with cover image, time elapsed and progress bar

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
- on initilisation the app will ask for your token which lasts for 1hr then needs to be refreshed.
- Visit the link provided in thonny then copy/paste the code found in your browser address bar: https://open.spotify.com/?code=''
