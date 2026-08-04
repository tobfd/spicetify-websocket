import uuid
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer

# --- Utility Helpers ---


def _convert_spotify_image_url(url: str | None) -> str | None:
    """Convert a Spotify image URL or raw image hash to a standard HTTP URL.

    Args:
        url: The Spotify image URL or hash to convert.

    Returns:
        The converted HTTP URL, or None if invalid or empty.
    """
    if not url:
        return None
    if url.startswith("spotify:image:"):
        image_id = url.replace("spotify:image:", "")
        return f"https://i.scdn.co/image/{image_id}"
    if not url.startswith("http://") and not url.startswith("https://"):
        return f"https://i.scdn.co/image/{url}"
    return url


def _parse_optional_bool(value: Any) -> bool | None:
    """Safely parse boolean values from raw JSON strings or booleans, returning None if missing."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        val_lower = value.lower()
        if val_lower in ("true", "1", "yes"):
            return True
        if val_lower in ("false", "0", "no"):
            return False
    return None


def _parse_optional_int(value: Any) -> int | None:
    """Safely parse integer values from raw JSON strings or numbers, returning None if missing."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_optional_float(value: Any) -> float | None:
    """Safely parse float values from raw JSON strings or numbers, returning None if missing."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _generate_id() -> str:
    """Generate a unique request ID.

    Returns:
        UUID string for matching requests and responses.
    """
    return str(uuid.uuid4())


# --- Internal Request Models ---


class _BaseRequest(BaseModel):
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
        """Serialize the request into the wire format expected by Spicetify."""
        data = handler(self)
        req_name = data.pop("requestName")
        req_id = data.pop("requestId")
        token = data.pop("token", None)

        serialized = {"requestName": req_name, "requestId": req_id, "payload": data}
        if token is not None:
            serialized["token"] = token
        return serialized


class _PlayRequest(_BaseRequest):
    """Internal request to start playback."""

    requestName: Literal["Play"] = "Play"


class _PauseRequest(_BaseRequest):
    """Internal request to pause playback."""

    requestName: Literal["Pause"] = "Pause"


class _TogglePlayRequest(_BaseRequest):
    """Internal request to toggle playback."""

    requestName: Literal["TogglePlay"] = "TogglePlay"


class _NextSongRequest(_BaseRequest):
    """Internal request to skip to the next song."""

    requestName: Literal["NextSong"] = "NextSong"


class _PreviousSongRequest(_BaseRequest):
    """Internal request to skip to the previous song."""

    requestName: Literal["PreviousSong"] = "PreviousSong"


class _ForcePreviousSongRequest(_BaseRequest):
    """Internal request to force skip to the previous song."""

    requestName: Literal["ForcePreviousSong"] = "ForcePreviousSong"


class _GetPlayerStateRequest(_BaseRequest):
    """Internal request to retrieve the current player state."""

    requestName: Literal["GetPlayerState"] = "GetPlayerState"


class _GetCurrentTrackRequest(_BaseRequest):
    """Internal request to retrieve the current track information."""

    requestName: Literal["GetCurrentTrack"] = "GetCurrentTrack"


class _GetVolumeRequest(_BaseRequest):
    """Internal request to retrieve the current playback volume."""

    requestName: Literal["GetVolume"] = "GetVolume"


class _GetPlayPauseRequest(_BaseRequest):
    """Internal request to retrieve the current play/pause state."""

    requestName: Literal["GetPlayPause"] = "GetPlayPause"


class _PingRequest(_BaseRequest):
    """Internal request to ping the Spicetify client."""

    requestName: Literal["Ping"] = "Ping"


class _SetShuffleRequest(_BaseRequest):
    """Internal request to enable or disable shuffle mode."""

    requestName: Literal["SetShuffle"] = "SetShuffle"
    state: bool = Field(..., description="True to enable shuffle, False to disable")


class _SetMuteRequest(_BaseRequest):
    """Internal request to mute or unmute playback."""

    requestName: Literal["SetMute"] = "SetMute"
    state: bool = Field(..., description="True to mute, False to unmute")


class _SeekRequest(_BaseRequest):
    """Internal request to seek to a specific position in the current track."""

    requestName: Literal["Seek"] = "Seek"
    position: int | float = Field(..., ge=0, description="Position in milliseconds to seek to")


class _SetVolumeRequest(_BaseRequest):
    """Internal request to set the playback volume."""

    requestName: Literal["SetVolume"] = "SetVolume"
    level: float | int = Field(..., ge=0.0, le=1.0, description="Volume between 0.0 and 1.0")


class _SetRepeatRequest(_BaseRequest):
    """Internal request to change the repeat mode."""

    requestName: Literal["SetRepeat"] = "SetRepeat"
    mode: int = Field(..., ge=0, le=2, description="0=Off, 1=Context, 2=Track")


class _PlayUriRequest(_BaseRequest):
    """Internal request to start playback from a Spotify URI or URL."""

    requestName: Literal["PlayUri"] = "PlayUri"
    uri: str


# --- Sub-Models for Metadata & Details ---


class ArtistInfo(BaseModel):
    """Metadata for an artist.

    Attributes:
        name: Artist name.
        uri: Spotify URI of the artist.
    """

    name: str
    uri: str

    def __str__(self) -> str:
        return f"{self.name} ({self.uri})"

    @property
    def url(self) -> str:
        """Return the Spotify web URL for the artist."""
        return f"https://open.spotify.com/artist/{self.uri.split(':')[-1]}"


class AlbumInfo(BaseModel):
    """Metadata for an album.

    Attributes:
        name: Album name.
        uri: Spotify URI of the album.
        images: List of artwork image URLs.
        release_date: Album release date (e.g. '2024-05-17T00:00:00Z', if available).
        disc_count: Total disc count on album (if available).
    """

    name: str
    uri: str
    images: list[str] = Field(default_factory=list)
    release_date: str | None = None
    disc_count: int | None = None

    def __str__(self) -> str:
        return f"{self.name} ({self.uri})"

    @property
    def url(self) -> str:
        """Return the Spotify web URL for the album."""
        return f"https://open.spotify.com/album/{self.uri.split(':')[-1]}"


class TrackImages(BaseModel):
    """Image URLs for a track in various resolutions.

    Attributes:
        small: Small cover artwork URL.
        standard: Standard cover artwork URL.
        large: Large cover artwork URL.
        xlarge: Extra-large cover artwork URL.
    """

    small: str | None = None
    standard: str | None = None
    large: str | None = None
    xlarge: str | None = None


class TrackInfo(BaseModel):
    """Metadata for a Spotify track.

    Attributes:
        uri: Spotify URI of the track.
        title: Track title.
        duration_ms: Track duration in milliseconds.
        artists: List of artists associated with the track.
        album: Album details object (None if missing).
        is_local: Whether the track is a local file.
        is_explicit: Whether the track is explicit.
        has_lyrics: Whether lyrics are available (None if unknown).
        popularity: Track popularity score 0-100 (None if unknown).
        image_url: Standard artwork image URL.
        images: Artwork images in various resolutions.
    """

    uri: str
    title: str
    duration_ms: int
    artists: list[ArtistInfo]
    album: AlbumInfo | None = None
    is_local: bool = False
    is_explicit: bool = False
    has_lyrics: bool | None = None
    popularity: int | None = None
    image_url: str | None = None
    images: TrackImages = Field(default_factory=TrackImages)

    def __str__(self) -> str:
        artist_names = (
            ", ".join(artist.name for artist in self.artists) if self.artists else "Unknown Artist"
        )
        album_name = self.album.name if self.album else "Unknown Album"
        return f"{self.title} by {artist_names} from the album '{album_name}'"

    @property
    def url(self) -> str:
        """Return the Spotify web URL for the track."""
        return f"https://open.spotify.com/track/{self.uri.split(':')[-1]}"

    @property
    def duration_seconds(self) -> float:
        """Return track duration in seconds."""
        return self.duration_ms / 1000.0

    @staticmethod
    def from_payload(payload: dict[str, Any]) -> "TrackInfo":
        """Create a TrackInfo instance from a raw Spicetify item payload."""
        track_data = (
            payload.get("track", payload)
            if isinstance(payload, dict) and "track" in payload
            else payload
        )
        if not isinstance(track_data, dict):
            track_data = {}

        meta = track_data.get("metadata", {})
        if not isinstance(meta, dict):
            meta = {}

        album_data = track_data.get("album", {})
        if not isinstance(album_data, dict):
            album_data = {}

        raw_artists = track_data.get("artists", [])
        artists = [
            ArtistInfo(
                name=artist.get("name", ""),
                uri=artist.get("uri", ""),
            )
            for artist in raw_artists
            if isinstance(artist, dict)
        ]

        duration = track_data.get("duration")
        if isinstance(duration, dict):
            duration_ms = _parse_optional_int(duration.get("milliseconds")) or 0
        else:
            duration_ms = _parse_optional_int(duration) or 0

        if not duration_ms and "duration" in meta:
            duration_ms = _parse_optional_int(meta.get("duration")) or 0

        album_images = []
        for img in album_data.get("images", []):
            if isinstance(img, dict):
                converted = _convert_spotify_image_url(img.get("url"))
                if converted:
                    album_images.append(converted)

        album_name = album_data.get("name") or meta.get("album_title")
        album_uri = album_data.get("uri") or meta.get("album_uri")
        release_date = (
            album_data.get("releaseDate")
            or album_data.get("release_date")
            or meta.get("releaseDate")
            or meta.get("release_date")
        )

        album = None
        if album_name or album_uri:
            album = AlbumInfo(
                name=album_name or "",
                uri=album_uri or "",
                images=album_images,
                release_date=release_date,
                disc_count=_parse_optional_int(meta.get("album_disc_count")),
            )

        img_small = _convert_spotify_image_url(meta.get("image_small_url"))
        img_standard = _convert_spotify_image_url(meta.get("image_url"))
        img_large = _convert_spotify_image_url(meta.get("image_large_url"))
        img_xlarge = _convert_spotify_image_url(meta.get("image_xlarge_url"))

        if not img_standard and album_images:
            img_standard = album_images[0]

        images_obj = TrackImages(
            small=img_small,
            standard=img_standard,
            large=img_large,
            xlarge=img_xlarge,
        )

        title = track_data.get("name") or meta.get("title") or ""

        return TrackInfo(
            uri=track_data.get("uri", ""),
            title=title,
            duration_ms=duration_ms,
            artists=artists,
            album=album,
            is_local=_parse_optional_bool(track_data.get("isLocal")) or False,
            is_explicit=_parse_optional_bool(track_data.get("isExplicit")) or False,
            has_lyrics=_parse_optional_bool(meta.get("has_lyrics")),
            popularity=_parse_optional_int(meta.get("popularity")),
            image_url=img_standard,
            images=images_obj,
        )


# --- Playback State Sub-Models ---


class RepeatMode(IntEnum):
    """Supported repeat modes."""

    OFF = 0
    CONTEXT = 1
    TRACK = 2


class PlaybackRestrictions(BaseModel):
    """Permissions for playback actions.

    Attributes:
        can_pause: Whether pausing is permitted.
        can_resume: Whether resuming is permitted.
        can_seek: Whether seeking is permitted.
        can_skip_previous: Whether skipping previous is permitted.
        can_skip_next: Whether skipping next is permitted.
        can_toggle_repeat_context: Whether toggling context repeat is permitted.
        can_toggle_repeat_track: Whether toggling track repeat is permitted.
        can_toggle_shuffle: Whether toggling shuffle is permitted.
        can_toggle_smart_shuffle: Whether toggling smart shuffle is permitted.
    """

    can_pause: bool = True
    can_resume: bool = True
    can_seek: bool = True
    can_skip_previous: bool = True
    can_skip_next: bool = True
    can_toggle_repeat_context: bool = True
    can_toggle_repeat_track: bool = True
    can_toggle_shuffle: bool = True
    can_toggle_smart_shuffle: bool = True

    @staticmethod
    def from_payload(data: dict[str, Any]) -> "PlaybackRestrictions":
        """Create PlaybackRestrictions instance from restrictions payload."""
        if not isinstance(data, dict):
            return PlaybackRestrictions()

        def _get_bool(key: str, default: bool = True) -> bool:
            parsed = _parse_optional_bool(data.get(key))
            return parsed if parsed is not None else default

        return PlaybackRestrictions(
            can_pause=_get_bool("canPause", True),
            can_resume=_get_bool("canResume", True),
            can_seek=_get_bool("canSeek", True),
            can_skip_previous=_get_bool("canSkipPrevious", True),
            can_skip_next=_get_bool("canSkipNext", True),
            can_toggle_repeat_context=_get_bool("canToggleRepeatContext", True),
            can_toggle_repeat_track=_get_bool("canToggleRepeatTrack", True),
            can_toggle_shuffle=_get_bool("canToggleShuffle", True),
            can_toggle_smart_shuffle=_get_bool("canToggleSmartShuffle", True),
        )


class PlaybackContext(BaseModel):
    """Context metadata (playlist, album, artist radio, etc.).

    Attributes:
        uri: Spotify URI of the playback context.
        description: Description string of context (e.g. Playlist or Album name).
        owner: Owner ID of the playlist/context.
        image_url: Context image URL.
        track_count: Number of tracks in playlist/context (None if unavailable).
    """

    uri: str | None = None
    description: str | None = None
    owner: str | None = None
    image_url: str | None = None
    track_count: int | None = None

    @property
    def url(self) -> str | None:
        """Return the Spotify web URL for the playback context."""
        if not self.uri or not self.uri.startswith("spotify:"):
            return None
        parts = self.uri.split(":")
        if len(parts) >= 3:
            return f"https://open.spotify.com/{parts[1]}/{parts[2]}"
        return None

    @property
    def owner_url(self) -> str | None:
        """Return the Spotify web URL for the context owner."""
        if not self.owner:
            return None
        return f"https://open.spotify.com/user/{self.owner}"

    @staticmethod
    def from_payload(data: dict[str, Any]) -> "PlaybackContext | None":
        """Create PlaybackContext instance from context payload."""
        if not isinstance(data, dict) or not data:
            return None

        meta = data.get("metadata", {})
        if not isinstance(meta, dict):
            meta = {}

        uri = data.get("uri")
        description = meta.get("context_description")

        if not uri and not description:
            return None

        return PlaybackContext(
            uri=uri,
            description=description,
            owner=meta.get("context_owner"),
            image_url=_convert_spotify_image_url(meta.get("image_url")),
            track_count=_parse_optional_int(meta.get("playlist_number_of_tracks")),
        )


class PlayerState(BaseModel):
    """Complete snapshot of the Spotify player state.

    Attributes:
        event_name: Name of the event that triggered this state snapshot.
        is_playing: Whether playback is currently active.
        is_muted: Whether audio output is muted.
        volume: Playback volume percentage (0.0 to 100.0).
        position_ms: Current playback position in milliseconds.
        duration_ms: Duration of current track in milliseconds.
        shuffle: Whether shuffle mode is enabled.
        smart_shuffle: Whether smart shuffle mode is enabled.
        repeat_mode: Current repeat mode enum.
        item_index: Index position of current track in context/playlist (None if unavailable).
        track: Currently loaded track metadata (None if no track active).
        context: Active playlist/context details (None if no context).
        restrictions: Permissions for playback control.
        timestamp: UTC timestamp of current player state.
        has_context: Whether active context exists.
        is_buffering: Whether stream is currently buffering.
        previous_tracks: List of previous track items.
        next_tracks: List of upcoming queue track items.
    """

    event_name: str | None = None
    is_playing: bool = False
    is_muted: bool = False
    volume: float = 0.0
    position_ms: int = 0
    duration_ms: int = 0
    shuffle: bool = False
    smart_shuffle: bool = False
    repeat_mode: RepeatMode = RepeatMode.OFF
    item_index: int | None = None
    track: TrackInfo | None = None
    context: PlaybackContext | None = None
    restrictions: PlaybackRestrictions = Field(default_factory=PlaybackRestrictions)
    timestamp: datetime | None = None
    has_context: bool = False
    is_buffering: bool = False
    previous_tracks: list[TrackInfo] = Field(default_factory=list)
    next_tracks: list[TrackInfo] = Field(default_factory=list)

    def __str__(self) -> str:
        """Return a human-readable string representation of the PlayerState."""
        event_str = self.event_name if self.event_name is not None else "None"
        track_info = str(self.track) if self.track is not None else "No track playing"
        return f"PlayerState(event={event_str}, is_playing={self.is_playing}, track={track_info})"

    @property
    def position_seconds(self) -> float:
        """Return current playback position in seconds."""
        return self.position_ms / 1000.0

    @property
    def duration_seconds(self) -> float:
        """Return total track duration in seconds."""
        return self.duration_ms / 1000.0

    @staticmethod
    def from_payload(payload: dict[str, Any], event_name: str | None = None) -> "PlayerState":
        """Build full PlayerState snapshot from raw extension payload."""
        if not isinstance(payload, dict):
            payload = {}

        player_data = payload.get("playerData")
        if not isinstance(player_data, dict):
            player_data = payload.get("playerState")
        if not isinstance(player_data, dict):
            player_data = payload

        # Context
        context_data = player_data.get("context", {})
        context = PlaybackContext.from_payload(
            context_data if isinstance(context_data, dict) else {}
        )

        # Extract track
        track = None
        item = player_data.get("item")
        if item and isinstance(item, dict):
            track = TrackInfo.from_payload(item)

        # If track album is missing release_date, try extracting from context metadata
        if (
            track
            and track.album
            and not track.album.release_date
            and isinstance(context_data, dict)
        ):
            ctx_meta = context_data.get("metadata", {})
            if isinstance(ctx_meta, dict) and "releaseDate" in ctx_meta:
                track.album.release_date = ctx_meta.get("releaseDate")

        # Queue
        prev_items = player_data.get("previousItems", [])
        previous_tracks = [TrackInfo.from_payload(t) for t in prev_items if isinstance(t, dict)]

        next_items = player_data.get("nextItems", [])
        next_tracks = [TrackInfo.from_payload(t) for t in next_items if isinstance(t, dict)]

        # Is playing
        is_playing_raw = payload.get("isPlaying")
        if is_playing_raw is None:
            is_playing_raw = player_data.get("isPlaying")
        if is_playing_raw is None:
            is_paused = _parse_optional_bool(player_data.get("isPaused"))
            is_playing = not is_paused if is_paused is not None else False
        else:
            is_playing = _parse_optional_bool(is_playing_raw) or False

        # Volume
        vol_raw = _parse_optional_float(payload.get("volume"))
        if vol_raw is None:
            vol_raw = _parse_optional_float(player_data.get("volume"))
        if vol_raw is not None:
            volume = round(vol_raw * 100, 2) if vol_raw <= 1.0 else vol_raw
        else:
            volume = 0.0

        # Muted
        is_muted_raw = payload.get("isMuted")
        if is_muted_raw is None:
            is_muted_raw = player_data.get("isMuted")
        is_muted = _parse_optional_bool(is_muted_raw) or False

        # Position (progress)
        pos_ms = _parse_optional_int(payload.get("progress"))
        if pos_ms is None:
            pos_ms = _parse_optional_int(player_data.get("positionAsOfTimestamp"))
        if pos_ms is None:
            pos_ms = _parse_optional_int(payload.get("position_as_of_timestamp"))
        if pos_ms is None:
            pos_ms = _parse_optional_int(player_data.get("position_as_of_timestamp")) or 0

        # Duration
        duration_ms = _parse_optional_int(player_data.get("duration"))
        if not duration_ms and track:
            duration_ms = track.duration_ms

        # Shuffle
        shuffle_raw = payload.get("shuffle")
        if shuffle_raw is None:
            shuffle_raw = player_data.get("shuffle")
        shuffle = _parse_optional_bool(shuffle_raw) or False

        # Smart Shuffle
        smart_shuffle_raw = payload.get("smartShuffle")
        if smart_shuffle_raw is None:
            smart_shuffle_raw = player_data.get("smartShuffle")
        smart_shuffle = _parse_optional_bool(smart_shuffle_raw) or False

        # Repeat
        repeat_raw = payload.get("repeat")
        if repeat_raw is None:
            repeat_raw = player_data.get("repeat")
        repeat_int = _parse_optional_int(repeat_raw)
        try:
            repeat_mode = RepeatMode(repeat_int) if repeat_int is not None else RepeatMode.OFF
        except ValueError:
            repeat_mode = RepeatMode.OFF

        # Item Index
        index_data = player_data.get("index")
        item_index = None
        if isinstance(index_data, dict):
            item_index = _parse_optional_int(index_data.get("itemIndex"))

        # Timestamp
        ts_raw = player_data.get("timestamp")
        dt_ts = None
        if isinstance(ts_raw, (int, float)):
            dt_ts = datetime.fromtimestamp(ts_raw / 1000.0, tz=timezone.utc)

        # Restrictions
        restr_data = player_data.get("restrictions", {})
        restrictions = PlaybackRestrictions.from_payload(
            restr_data if isinstance(restr_data, dict) else {}
        )

        return PlayerState(
            event_name=event_name,
            is_playing=is_playing,
            is_muted=is_muted,
            volume=volume,
            position_ms=pos_ms,
            duration_ms=duration_ms or 0,
            shuffle=shuffle,
            smart_shuffle=smart_shuffle,
            repeat_mode=repeat_mode,
            item_index=item_index,
            track=track,
            context=context,
            restrictions=restrictions,
            timestamp=dt_ts,
            has_context=_parse_optional_bool(player_data.get("hasContext")) or False,
            is_buffering=_parse_optional_bool(player_data.get("isBuffering")) or False,
            previous_tracks=previous_tracks,
            next_tracks=next_tracks,
        )
