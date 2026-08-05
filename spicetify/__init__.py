__title__ = "spicetify-websocket"
__license__ = "MIT"
__version__ = "0.3.1"

from .exceptions import NotConnectedError, RequestTimeoutError, SpicetifyError, UnauthorizedError
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
from .server import SpotifyServer

__all__ = [
    "AlbumInfo",
    "ArtistInfo",
    "NotConnectedError",
    "PlaybackContext",
    "PlaybackRestrictions",
    "PlayerState",
    "RepeatMode",
    "RequestTimeoutError",
    "SpicetifyError",
    "SpotifyServer",
    "TrackImages",
    "TrackInfo",
    "UnauthorizedError",
    "__version__",
]
