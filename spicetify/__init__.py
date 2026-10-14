__title__ = "spicetify-websocket"
__license__ = "MIT"
__version__ = "0.4.0"

from .exceptions import (
    NotConnectedError,
    RequestFailedError,
    RequestTimeoutError,
    SpicetifyError,
    UnauthorizedError,
)
from .models import (
    AlbumInfo,
    ArtistInfo,
    PlaybackContext,
    PlaybackRestrictions,
    PlayerState,
    RepeatMode,
    TrackImages,
    TrackInfo,
)
from .server import SPOTIFY_DESKTOP_ORIGIN, SUPPORTED_PROTOCOL_VERSION, SpotifyServer

__all__ = [
    "SPOTIFY_DESKTOP_ORIGIN",
    "SUPPORTED_PROTOCOL_VERSION",
    "AlbumInfo",
    "ArtistInfo",
    "NotConnectedError",
    "PlaybackContext",
    "PlaybackRestrictions",
    "PlayerState",
    "RepeatMode",
    "RequestFailedError",
    "RequestTimeoutError",
    "SpicetifyError",
    "SpotifyServer",
    "TrackImages",
    "TrackInfo",
    "UnauthorizedError",
    "__version__",
]
