__title__ = "spicetify-websocket"
__license__ = "MIT"
__version__ = "0.1.0"

from .exceptions import NotConnectedError, RequestTimeoutError, SpicetifyError
from .models import ArtistInfo, PlayerState, RepeatMode, TrackInfo
from .server import SpotifyServer

__all__ = [
    "ArtistInfo",
    "NotConnectedError",
    "PlayerState",
    "RepeatMode",
    "RequestTimeoutError",
    "SpicetifyError",
    "SpotifyServer",
    "TrackInfo",
    "__version__",
]
