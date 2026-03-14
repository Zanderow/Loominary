"""SpotifyOAuth PKCE, token caching, auto-refresh."""
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from loominary import config

SCOPES = "user-read-private"


def get_spotify_client() -> spotipy.Spotify:
    """Return an authenticated Spotipy client with token caching."""
    config.validate_spotify()
    auth_manager = SpotifyOAuth(
        client_id=config.SPOTIPY_CLIENT_ID,
        client_secret=config.SPOTIPY_CLIENT_SECRET,
        redirect_uri=config.SPOTIPY_REDIRECT_URI,
        scope=SCOPES,
        cache_path=".cache",
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth_manager)
