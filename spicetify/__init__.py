__title__ = "spicetify-websocket"
__license__ = "MIT"
__version__ = "0.2.0"

from .exceptions import NotConnectedError, RequestTimeoutError, SpicetifyError, UnauthorizedError
from .models import ArtistInfo, PingRequest, PlayerState, RepeatMode, TrackInfo
from .server import SpotifyServer

__all__ = [
    "ArtistInfo",
    "NotConnectedError",
    "PingRequest",
    "PlayerState",
    "RepeatMode",
    "RequestTimeoutError",
    "SpicetifyError",
    "SpotifyServer",
    "TrackInfo",
    "UnauthorizedError",
    "__version__",
]
