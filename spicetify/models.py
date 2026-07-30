import uuid
from enum import IntEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer

# --- Utility Helpers ---


def _convert_spotify_image_url(url: str) -> str:
    """Convert a Spotify image URL to a standard HTTP URL.

    Args:
        url: The Spotify image URL to convert.

    Returns:
        The converted HTTP URL, or the original URL if it doesn't match the expected format.
    """
    if url and url.startswith("spotify:image:"):
        image_id = url.replace("spotify:image:", "")
        return f"https://i.scdn.co/image/{image_id}"
    return url


def _generate_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())


# --- Request Models ---


class BaseRequest(BaseModel):
    """Base model for requests sent to Spicetify.

    The serialized form contains `requestName`, `requestId`, an optional `token`,
    and a nested `payload` object with the remaining fields.

    Attributes:
        requestName: The request type name sent over the wire.
        requestId: Unique request identifier used to match responses.
        token: Optional API key token for authorization.
    """

    requestName: str
    requestId: str = Field(default_factory=_generate_id)
    token: str | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler) -> dict:
        """Serialize the request into the wire format expected by Spicetify.

        Returns:
            Serialized request with `requestName`, `requestId`, optional `token`,
            and nested `payload`.
        """
        data = handler(self)

        req_name = data.pop("requestName")
        req_id = data.pop("requestId")
        token = data.pop("token", None)

        serialized = {"requestName": req_name, "requestId": req_id, "payload": data}
        if token is not None:
            serialized["token"] = token

        return serialized


# --- Playback control requests ---


class PlayRequest(BaseRequest):
    """Request to start playback."""

    requestName: Literal["Play"] = "Play"


class TogglePlayRequest(BaseRequest):
    """Request to toggle playback."""

    requestName: Literal["TogglePlay"] = "TogglePlay"


class NextSongRequest(BaseRequest):
    """Request to skip to the next song."""

    requestName: Literal["NextSong"] = "NextSong"


class PreviousSongRequest(BaseRequest):
    """Request to skip to the previous song."""

    requestName: Literal["PreviousSong"] = "PreviousSong"


class ForcePreviousSongRequest(BaseRequest):
    """Request to force skip to the previous song."""

    requestName: Literal["ForcePreviousSong"] = "ForcePreviousSong"


# --- State Query Requests ---
class GetPlayerStateRequest(BaseRequest):
    """Request to retrieve the current player state."""

    requestName: Literal["GetPlayerState"] = "GetPlayerState"


class GetCurrentTrackRequest(BaseRequest):
    """Request to retrieve the current track information."""

    requestName: Literal["GetCurrentTrack"] = "GetCurrentTrack"


class GetVolumeRequest(BaseRequest):
    """Request to retrieve the current playback volume."""

    requestName: Literal["GetVolume"] = "GetVolume"


class GetPlayPauseRequest(BaseRequest):
    """Request to retrieve the current play/pause state."""

    requestName: Literal["GetPlayPause"] = "GetPlayPause"


class PauseRequest(BaseRequest):
    """Request to pause playback."""

    requestName: Literal["Pause"] = "Pause"


class PingRequest(BaseRequest):
    """Request to ping the Spicetify client."""

    requestName: Literal["Ping"] = "Ping"


# --- Playback Setting Requests ---


class SetShuffleRequest(BaseRequest):
    """Request to enable or disable shuffle mode.

    Attributes:
        state: True to enable shuffle, False to disable.
    """

    requestName: Literal["SetShuffle"] = "SetShuffle"
    state: bool = Field(..., description="True to enable shuffle, False to disable")


class SetMuteRequest(BaseRequest):
    """Request to mute or unmute the playback.

    Attributes:
        state: True to mute, False to unmute.
    """

    requestName: Literal["SetMute"] = "SetMute"
    state: bool = Field(..., description="True to mute, False to unmute")


class SeekRequest(BaseRequest):
    """Request to seek to a specific position in the current track.

    Attributes:
        position: Position in milliseconds to seek to.
    """

    requestName: Literal["Seek"] = "Seek"
    position: int | float = Field(..., ge=0, description="Position in milliseconds to seek to")


class SetVolumeRequest(BaseRequest):
    """Request to set the playback volume.

    Attributes:
        level: Desired volume level between 0.0 and 1.0.
    """

    requestName: Literal["SetVolume"] = "SetVolume"
    level: float | int = Field(..., ge=0.0, le=1.0, description="Volume between 0.0 and 1.0")


class SetRepeatRequest(BaseRequest):
    """Request to change the repeat mode.

    Attributes:
        mode: Repeat mode, where 0 means off, 1 means context, and 2 means track.
    """

    requestName: Literal["SetRepeat"] = "SetRepeat"
    mode: int = Field(..., ge=0, le=2, description="0=Off, 1=Context, 2=Track")


class PlayUriRequest(BaseRequest):
    """Request to start playback from a Spotify URI or URL.

    Attributes:
        uri: Spotify URI/URL to play.
    """

    requestName: Literal["PlayUri"] = "PlayUri"
    uri: str


# --- Metadata Models ---


class ArtistInfo(BaseModel):
    """Metadata for an artist.

    Attributes:
        name: Artist name.
        uri: Spotify URI of the artist.
    """

    name: str
    uri: str

    def __str__(self) -> str:
        """Return a human-readable string representation of the artist."""
        return f"{self.name} ({self.uri})"

    @property
    def url(self) -> str:
        """Return the Spotify web URL for the artist.

        Returns:
            Spotify web URL for the artist.
        """
        return f"https://open.spotify.com/artist/{self.uri.split(':')[-1]}"


class TrackInfo(BaseModel):
    """Metadata for the currently playing track.

    Attributes:
        uri: Spotify URI of the track.
        title: Track title.
        duration_ms: Track duration in milliseconds.
        artists: List of artists associated with the track.
        album_name: Name of the album.
        album_uri: Spotify URI of the album.
        image_url: URL of the album artwork image. Default is None if not available.
        is_explicit: Whether the track is marked as explicit. Default is False.
    """

    uri: str
    title: str
    duration_ms: int
    artists: list[ArtistInfo]
    album_name: str
    album_uri: str
    image_url: str | None = None
    is_explicit: bool = False

    def __str__(self) -> str:
        """Return a human-readable string representation of the track."""
        artist_names = ", ".join(artist.name for artist in self.artists)
        return f"{self.title} by {artist_names} from the album '{self.album_name}'"

    @property
    def url(self) -> str:
        """Return the Spotify web URL for the track.

        Returns:
            Spotify web URL for the track.
        """
        return f"https://open.spotify.com/track/{self.uri.split(':')[-1]}"

    @property
    def album_url(self) -> str:
        """Return the Spotify web URL for the album.

        Returns:
            Spotify web URL for the album.
        """
        return f"https://open.spotify.com/album/{self.album_uri.split(':')[-1]}"

    @property
    def duration_seconds(self) -> float | int:
        """Return the track duration in seconds.

        Returns:
            Track duration in seconds.
        """
        return self.duration_ms / 1000

    @staticmethod
    def from_payload(payload: dict[str, Any]) -> "TrackInfo":
        """Create a TrackInfo instance from a payload dictionary.

        Args:
            payload: Payload containing track information.

        Returns:
            A :class:`TrackInfo` instance populated from the payload.
        """
        track_data = payload.get("track", {})
        metadata = track_data.get("metadata", {})

        raw_artists = track_data.get("artists", [])
        artists = [
            ArtistInfo(name=artist.get("name", ""), uri=artist.get("uri", ""))
            for artist in raw_artists
        ]

        duration = track_data.get("duration", {})
        if isinstance(duration, dict):
            duration_ms = duration.get("milliseconds", 0)
        else:
            duration_ms = int(duration) if duration else 0

        images = track_data.get("images", [])
        has_image = False
        raw_image_url = ""
        if images and len(images) > 0:
            has_image = True
            raw_image_url = images[0].get("url", "")
        elif "image_url" in metadata:
            has_image = True
            raw_image_url = metadata.get("image_url", "")

        image_url = _convert_spotify_image_url(raw_image_url) if has_image else None

        return TrackInfo(
            uri=track_data.get("uri", ""),
            title=track_data.get("name", ""),
            duration_ms=duration_ms,
            artists=artists,
            album_name=track_data.get("album", {}).get("name", ""),
            album_uri=track_data.get("album", {}).get("uri", ""),
            image_url=image_url,
            is_explicit=track_data.get("isExplicit", False),
        )


# --- Playback State Models ---


class RepeatMode(IntEnum):
    """Enumeration of supported repeat modes."""

    OFF = 0
    CONTEXT = 1
    TRACK = 2


class PlayerState(BaseModel):
    """Represents the current Spotify player state.

    Attributes:
        is_playing: Whether playback is currently active.
        position_ms: Current playback position in milliseconds.
        duration_ms: Total duration of the current track in milliseconds.
        shuffle: Whether shuffle mode is enabled.
        smart_shuffle: Whether smart shuffle mode is enabled.
        repeat_mode: Current repeat mode. See :class:`RepeatMode`.
        track: Information about the current track, if available.
            See :class:`TrackInfo`.
        context_uri: Spotify URI of the current playback context, if available.
    """

    is_playing: bool
    position_ms: int
    duration_ms: int
    shuffle: bool
    smart_shuffle: bool
    repeat_mode: RepeatMode
    track: TrackInfo | None = None
    context_uri: str | None = None

    def __str__(self) -> str:
        """Return a human-readable string of the PlayerState"""
        track_info = str(self.track) if self.track else "No track playing"
        return (
            f"PlayerState:\n"
            f"  Is Playing: {self.is_playing}\n"
            f"  Position: {self.position_ms} ms\n"
            f"  Duration: {self.duration_ms} ms\n"
            f"  Shuffle: {self.shuffle}\n"
            f"  Smart Shuffle: {self.smart_shuffle}\n"
            f"  Repeat Mode: {self.repeat_mode.name}\n"
            f"  Track Info: {track_info}\n"
            f"  Context URI: {self.context_uri}"
        )

    @property
    def position_seconds(self) -> float | int:
        """Return the current playback position in seconds.

        Returns:
            Current playback position in seconds.
        """
        return self.position_ms / 1000

    @property
    def duration_seconds(self) -> float | int:
        """Return the total duration of the current track in seconds.

        Returns:
            Total duration of the current track in seconds.
        """
        return self.duration_ms / 1000

    @property
    def context_url(self) -> str | None:
        """Return the Spotify web URL for the current playback context.

        Returns:
            Spotify web URL for the context, or None if not available.
        """
        if self.context_uri:
            return f"https://open.spotify.com/{self.context_uri.split(':')[1]}/{self.context_uri.split(':')[-1]}"
        return None

    @staticmethod
    def from_payload(payload: dict[str, Any]) -> "PlayerState":
        """Create a PlayerState instance from a payload dictionary.

        Args:
            payload: Payload containing player state information.

        Returns:
            A :class:`PlayerState` instance populated with data from the
            payload.
        """
        track = None
        item = payload.get("item")
        if item and isinstance(item, dict):
            track = TrackInfo.from_payload({"track": item})

        context = payload.get("context", {})
        context_uri = context.get("uri") if isinstance(context, dict) else None

        is_paused = payload.get("isPaused", True)
        is_playing = not is_paused

        position_ms = payload.get("positionAsOfTimestamp", 0)
        duration_ms = payload.get("duration", 0)

        shuffle = payload.get("shuffle", False)
        smart_shuffle = payload.get("smartShuffle", False)
        repeat_mode = RepeatMode(payload.get("repeat", 0))

        return PlayerState(
            is_playing=is_playing,
            position_ms=position_ms,
            duration_ms=duration_ms,
            shuffle=shuffle,
            smart_shuffle=smart_shuffle,
            repeat_mode=repeat_mode,
            track=track,
            context_uri=context_uri,
        )
