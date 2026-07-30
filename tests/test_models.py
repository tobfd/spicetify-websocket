"""Tests for data models and request serialization."""

from spicetify import ArtistInfo, PingRequest, PlayerState, RepeatMode, TrackInfo
from spicetify.models import SetVolumeRequest, _convert_spotify_image_url


def test_artist_info_url():
    """Test ArtistInfo string representation and web URL generation."""
    artist = ArtistInfo(name="Test Artist", uri="spotify:artist:12345")
    assert artist.url == "https://open.spotify.com/artist/12345"
    assert str(artist) == "Test Artist (spotify:artist:12345)"


def test_set_volume_request_serialization():
    """Test serialization of SetVolumeRequest to Spicetify wire format."""
    req = SetVolumeRequest(level=0.75, token="secret123")
    data = req.model_dump(exclude_none=True)
    assert data["requestName"] == "SetVolume"
    assert "requestId" in data
    assert data["payload"]["level"] == 0.75
    assert data["token"] == "secret123"


def test_ping_request_serialization():
    """Test serialization of PingRequest."""
    req = PingRequest(token="auth-key")
    data = req.model_dump(exclude_none=True)
    assert data["requestName"] == "Ping"
    assert "requestId" in data
    assert data["payload"] == {}
    assert data["token"] == "auth-key"


def test_track_info_parsing_and_properties():
    """Test parsing TrackInfo model and accessing helper properties."""
    payload = {
        "track": {
            "uri": "spotify:track:abc",
            "name": "Test Song",
            "duration": {"milliseconds": 180000},
            "artists": [{"name": "Artist 1", "uri": "spotify:artist:1"}],
            "album": {"name": "Test Album", "uri": "spotify:album:2"},
            "metadata": {"image_url": "spotify:image:ab1234"},
        }
    }
    track = TrackInfo.from_payload(payload)
    assert track.title == "Test Song"
    assert track.duration_seconds == 180.0
    assert track.album_url == "https://open.spotify.com/album/2"
    assert track.url == "https://open.spotify.com/track/abc"
    assert track.image_url == "https://i.scdn.co/image/ab1234"
    assert "Test Song by Artist 1" in str(track)


def test_player_state_parsing_and_properties():
    """Test parsing PlayerState model and accessing helper properties."""
    payload = {
        "isPaused": False,
        "positionAsOfTimestamp": 10000,
        "duration": 200000,
        "shuffle": True,
        "smartShuffle": False,
        "repeat": 1,
        "context": {"uri": "spotify:playlist:123"},
    }
    state = PlayerState.from_payload(payload)
    assert state.is_playing is True
    assert state.position_seconds == 10.0
    assert state.duration_seconds == 200.0
    assert state.repeat_mode == RepeatMode.CONTEXT
    assert state.context_url == "https://open.spotify.com/playlist/123"
    assert "PlayerState:" in str(state)


def test_models_edge_cases():
    """Test remaining edge cases in models.py for full coverage."""
    assert (
        _convert_spotify_image_url("https://example.com/pic.jpg") == "https://example.com/pic.jpg"
    )
    assert _convert_spotify_image_url("") == ""

    track_no_img = TrackInfo.from_payload({"track": {"name": "No Image Track", "images": []}})
    assert track_no_img.image_url is None

    state_no_ctx = PlayerState.from_payload({})
    assert state_no_ctx.context_url is None
    assert state_no_ctx.track is None
