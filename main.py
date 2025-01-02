#https://github.com/mrglennjones/presto-spotify

import gc
import sdcard
import machine
import uos
import jpegdec
from presto import Presto
import utime as time
from time import sleep
import network
import secrets
import json
import urequests  # Ensure this is included

# Initialize Presto with high brightness
presto = Presto(ambient_light=False)  # Disable ambient light sensor for consistent brightness
presto.set_backlight(1.0)  # Maximum brightness
display = presto.display
WIDTH, HEIGHT = display.get_bounds()
jpeg = jpegdec.JPEG(display)

# File paths
TOKEN_FILE = "/sd/token.json"
IMAGE_FILE = "/sd/nowplaying.jpg"

# Spotify credentials from secrets.py
CLIENT_ID = secrets.CLIENT_ID
CLIENT_SECRET = secrets.CLIENT_SECRET
REDIRECT_URI = secrets.REDIRECT_URI
ACCESS_TOKEN = None  # Will be set dynamically
WIFI_SSID = secrets.WIFI_SSID
WIFI_PASSWORD = secrets.WIFI_PASSWORD

# Cache for the last song ID
last_song_id = None


def connect_to_wifi():
    """
    Connects to Wi-Fi using credentials from secrets.py.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    display_text_on_screen("Connecting to Wi-Fi...")
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            sleep(1)
            display_text_on_screen("Connecting to Wi-Fi...")
    ip_address = wlan.ifconfig()[0]
    display_text_on_screen(f"Wi-Fi Connected\nIP: {ip_address}")
    print(f"Connected to Wi-Fi! IP Address: {ip_address}")


def mount_sd():
    """
    Mounts the SD card to the '/sd' directory.
    """
    try:
        display_text_on_screen("Initializing SD Card...")
        sd_spi = machine.SPI(0,
                             sck=machine.Pin(34, machine.Pin.OUT),
                             mosi=machine.Pin(35, machine.Pin.OUT),
                             miso=machine.Pin(36, machine.Pin.OUT))
        sd = sdcard.SDCard(sd_spi, machine.Pin(39))
        uos.mount(sd, "/sd")
        display_text_on_screen("SD Card Mounted")
        print("SD card mounted successfully!")
    except Exception as e:
        display_text_on_screen("SD Card Mount Failed")
        print(f"Error mounting SD card: {e}")


def save_token(token_data):
    """
    Saves the access token, refresh token, and their expiration time to a file on the SD card.
    """
    token_data['expires_at'] = int(time.time()) + token_data['expires_in']
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f)
        print(f"Token data saved to {TOKEN_FILE}")
    except OSError as e:
        print(f"Error saving token to SD card: {e}")


def load_token():
    """
    Loads the access token and its expiration time from a file on the SD card.
    """
    try:
        with open(TOKEN_FILE, "r") as f:
            token_data = json.load(f)
            if token_data['expires_at'] > time.time():
                print("Loaded valid token from SD card.")
                return token_data
            else:
                print("Token has expired.")
                return None
    except OSError as e:
        print(f"Error loading token from SD card: {e}")
        return None


def refresh_token():
    """
    Uses the refresh token to request a new access token.
    """
    global ACCESS_TOKEN
    try:
        with open(TOKEN_FILE, "r") as f:
            token_data = json.load(f)

        if "refresh_token" not in token_data:
            raise ValueError("Refresh token not found in token data.")

        refresh_token = token_data["refresh_token"]

        token_url = "https://accounts.spotify.com/api/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = (
            f"grant_type=refresh_token"
            f"&refresh_token={refresh_token}"
            f"&client_id={CLIENT_ID}"
            f"&client_secret={CLIENT_SECRET}"
        )

        response = urequests.post(token_url, headers=headers, data=data)

        if response.status_code == 200:
            new_token_data = response.json()
            print(f"New Token Data: {new_token_data}")

            # Update and save the new access token and expiration time
            token_data['access_token'] = new_token_data['access_token']
            token_data['expires_in'] = new_token_data.get('expires_in', 3600)
            token_data['expires_at'] = int(time.time()) + token_data['expires_in']

            # Save any new refresh token (if provided)
            if "refresh_token" in new_token_data:
                token_data["refresh_token"] = new_token_data["refresh_token"]

            save_token(token_data)
            ACCESS_TOKEN = new_token_data['access_token']
            print("Access token refreshed successfully!")
        else:
            print(f"Failed to refresh token: {response.status_code}")
            print(response.text)
            raise ValueError("Failed to refresh access token.")
    except Exception as e:
        print(f"Error refreshing token: {e}")
        raise


def spotify_auth():
    """
    Authenticate with Spotify API using Authorization Code Flow and save the token to SD card.
    """
    global ACCESS_TOKEN

    # Attempt to load an existing token
    token_data = load_token()
    if token_data:
        ACCESS_TOKEN = token_data['access_token']
        return  # Token is valid and loaded

    # If no valid token, proceed with authentication
    print("Go to this URL to authorize the app:")
    auth_url = (
        f"https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=user-read-playback-state user-modify-playback-state"
    )
    print(auth_url)

    auth_code = input("Enter the authorization code from the URL: ")

    token_url = "https://accounts.spotify.com/api/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = (
        f"grant_type=authorization_code&code={auth_code}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&client_id={CLIENT_ID}"
        f"&client_secret={CLIENT_SECRET}"
    )

    response = urequests.post(token_url, headers=headers, data=data)

    if response.status_code == 200:
        token_data = response.json()
        print(f"Token Data: {token_data}")
        ACCESS_TOKEN = token_data['access_token']
        save_token(token_data)  # Save token to SD card
        print("Access token retrieved and saved successfully!")
    else:
        print(f"Error during authentication: {response.status_code}")
        print(response.text)
        raise ValueError("Failed to retrieve access token.")


def get_now_playing():
    """
    Fetches the currently playing song information from Spotify.
    Automatically refreshes the token if it's expired.
    """
    global ACCESS_TOKEN

    try:
        # Check if the token is expired
        token_data = load_token()
        if not token_data or token_data["expires_at"] <= time.time():
            print("Access token expired, refreshing...")
            refresh_token()
            token_data = load_token()  # Reload token after refresh
            if not token_data:
                raise ValueError("Failed to load refreshed token.")
            ACCESS_TOKEN = token_data["access_token"]

        # Use the access token to fetch now-playing info
        url = "https://api.spotify.com/v1/me/player/currently-playing"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        response = urequests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 204:
            print("No content: nothing is currently playing.")
            return None
        else:
            print(f"Error fetching now-playing: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"Error in get_now_playing: {e}")
        return None



def save_image_to_sd(image_data):
    """
    Saves the album art to the SD card with the name 'nowplaying.jpg'.
    """
    try:
        with open(IMAGE_FILE, "wb") as f:
            f.write(image_data)
        print(f"Album art saved to {IMAGE_FILE}")
        return IMAGE_FILE
    except OSError as e:
        print(f"Error saving album art: {e}")
        return None


def display_now_playing_image(filepath=None, song_name="", artist_name="", progress_ms=0, duration_ms=0):
    """
    Displays an image scaled to 25% of its original size on a black background
    with the song title (multiline, below the image), artist name centered below the song title,
    and a progress bar with playback position and duration.
    """
    filepath = filepath or IMAGE_FILE
    print("Attempting to display image:", filepath)

    try:
        # Set black background
        display.set_pen(display.create_pen(0, 0, 0))  # Black background
        display.clear()

        # Open the JPEG file
        jpeg.open_file(filepath)

        # Get original image dimensions
        img_width, img_height = jpeg.get_width(), jpeg.get_height()
        print(f"Original image dimensions: {img_width}x{img_height}")

        # Scale the image to 25% of its original size
        scale = jpegdec.JPEG_SCALE_HALF
        scaled_width = img_width // 2
        scaled_height = img_height // 2

        # Position the image with a 10-pixel margin from the top
        img_x = (WIDTH - scaled_width) // 2
        img_y = 10  # 10-pixel margin from the top

        print(f"Decoding image at ({img_x}, {img_y}) with scale {scale}")
        jpeg.decode(img_x, img_y, scale, dither=True)

        # Overlay song title and artist name in white
        display.set_pen(display.create_pen(255, 255, 255))  # White text

        # Handle multiline song title
        title_font_scale = 2  # Smaller font size
        line_height = 12      # Line height for wrapping
        title_max_width = WIDTH - 20  # Padding for text
        title_lines = wrap_text(song_name, title_max_width, title_font_scale)
        title_total_height = len(title_lines) * line_height
        title_y_start = img_y + scaled_height + 10

        # Render each line of the song title
        for i, line in enumerate(title_lines):
            line_x = (WIDTH - display.measure_text(line, scale=title_font_scale)) // 2
            line_y = title_y_start + (i * line_height)
            display.text(line, line_x, line_y, WIDTH, title_font_scale)

        # Artist name: centered below the song title
        artist_font_scale = 1
        artist_x = (WIDTH - display.measure_text(artist_name, scale=artist_font_scale)) // 2
        artist_y = title_y_start + title_total_height + 10  # Below the song title
        display.text(artist_name, artist_x, artist_y, WIDTH, artist_font_scale)

        # Render playback position and duration
        playback_y = artist_y + 20
        current_time = format_ms(progress_ms)
        total_time = format_ms(duration_ms)
        playback_text = f"{current_time} / {total_time}"
        playback_x = (WIDTH - display.measure_text(playback_text, scale=1)) // 2

        # Set color to match progress bar background
        display.set_pen(display.create_pen(50, 50, 50))  # Gray color for playback text
        display.text(playback_text, playback_x, playback_y, WIDTH, 1)

        # Draw a progress bar below the playback text
        bar_y = playback_y + 15
        bar_x_start = 20
        bar_x_end = WIDTH - 20
        bar_width = bar_x_end - bar_x_start
        progress_width = int((progress_ms / duration_ms) * bar_width) if duration_ms > 0 else 0

        # Draw the progress bar background
        display.set_pen(display.create_pen(50, 50, 50))  # Gray bar
        display.rectangle(bar_x_start, bar_y, bar_width, 5)

        # Draw the progress bar foreground
        display.set_pen(display.create_pen(0, 200, 0))  # Green bar
        display.rectangle(bar_x_start, bar_y, progress_width, 5)

        # Update the screen
        presto.update()
        print("Image and text successfully displayed.")
    except Exception as e:
        print(f"Error displaying image: {e}")



def wrap_text(text, max_width, font_scale):
    """
    Wraps text into multiple lines that fit within the given width.
    """
    words = text.split(" ")
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        if display.measure_text(test_line, scale=font_scale) <= max_width:
            current_line.append(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def format_ms(milliseconds):
    """
    Converts milliseconds into a formatted MM:SS string.
    """
    seconds = (milliseconds // 1000) % 60
    minutes = (milliseconds // 60000) % 60
    return f"{minutes:02}:{seconds:02}"


def draw_now_playing(info):
    """
    Displays the currently playing song metadata and album art on the Presto display.
    """
    global last_song_id
    display.clear()

    if info:
        song_id = info['item']['id']  # Unique ID for the current song
        song_name = info['item']['name']
        artist_name = ', '.join(artist['name'] for artist in info['item']['artists'])
        album_art_url = None

        # Select the 320x320 image if available
        album_images = info['item']['album']['images']
        if len(album_images) > 1:
            album_art_url = album_images[1]['url']  # Typically the 320x320 image
        else:
            album_art_url = album_images[0]['url']  # Fallback to the first image

        progress_ms = info['progress_ms']
        duration_ms = info['item']['duration_ms']

        print(f"Song: {song_name}, Artist: {artist_name}, Progress: {progress_ms} ms, Duration: {duration_ms} ms")
        print(f"Using Album Art URL: {album_art_url}")

        # Check if the song is the same as the last one
        if song_id == last_song_id:
            print("Same song detected, skipping album art download.")
            display_now_playing_image(IMAGE_FILE, song_name, artist_name, progress_ms, duration_ms)
        else:
            print("New song detected, downloading album art.")
            try:
                response = urequests.get(album_art_url)
                if response.status_code == 200:
                    image_data = response.content
                    filepath = save_image_to_sd(image_data)
                    if filepath:
                        display_now_playing_image(filepath, song_name, artist_name, progress_ms, duration_ms)
                        last_song_id = song_id  # Update the last song ID
                else:
                    print("Failed to fetch album art.")
            except Exception as e:
                print(f"Error handling album art: {e}")

    display.update()



def display_text_on_screen(message):
    """
    Displays a message on the Presto screen with a black background and white text.
    """
    display.set_pen(display.create_pen(0, 0, 0))  # Black background
    display.clear()
    display.set_pen(display.create_pen(255, 255, 255))  # White text
    display.text(message, 10, 85, WIDTH, 2)
    presto.update()
    sleep(1)


def main():
    """
    Main function that sets up the environment and starts the Spotify Now Playing loop.
    """
    connect_to_wifi()
    mount_sd()
    spotify_auth()

    while True:
        now_playing = get_now_playing()
        if now_playing:
            draw_now_playing(now_playing)
        sleep(5)


if __name__ == "__main__":
    main()


