"""Tests for data models, request serialization, and payload parsing."""

from spicetify import (
    AlbumInfo,
    ArtistInfo,
    PlaybackContext,
    PlaybackRestrictions,
    PlayerState,
    RepeatMode,
    TrackImages,
    TrackInfo,
)
from spicetify.models import _convert_spotify_image_url, _PingRequest, _SetVolumeRequest


def test_artist_info_url():
    """Test ArtistInfo string representation and web URL generation."""
    artist = ArtistInfo(name="Test Artist", uri="spotify:artist:12345")
    assert artist.url == "https://open.spotify.com/artist/12345"
    assert str(artist) == "Test Artist (spotify:artist:12345)"


def test_album_info_properties():
    """Test AlbumInfo string representation and web URL generation."""
    album = AlbumInfo(
        name="Test Album",
        uri="spotify:album:abc123",
        images=["https://i.scdn.co/image/img1"],
        disc_count=2,
    )
    assert album.url == "https://open.spotify.com/album/abc123"
    assert str(album) == "Test Album (spotify:album:abc123)"
    assert album.disc_count == 2


def test_track_images_and_conversion():
    """Test Spotify image URI to HTTP conversion helper."""
    converted = _convert_spotify_image_url("spotify:image:ab1234")
    assert converted == "https://i.scdn.co/image/ab1234"

    raw_url = "https://example.com/cover.jpg"
    assert _convert_spotify_image_url(raw_url) == raw_url
    assert _convert_spotify_image_url(None) is None
    assert _convert_spotify_image_url("") is None

    images = TrackImages(standard=converted)
    assert images.standard == "https://i.scdn.co/image/ab1234"
    assert images.small is None


def test_track_info_from_payload_full():
    """Test parsing a complete TrackInfo payload with metadata."""
    payload = {
        "uri": "spotify:track:xyz",
        "name": "Full Track",
        "duration": {"milliseconds": 200000},
        "isExplicit": True,
        "isLocal": False,
        "artists": [{"name": "A1", "uri": "spotify:artist:1"}],
        "album": {
            "name": "Test Album",
            "uri": "spotify:album:2",
            "images": [{"url": "spotify:image:img123"}],
        },
        "metadata": {
            "has_lyrics": "true",
            "popularity": "90",
            "image_small_url": "spotify:image:small123",
            "image_url": "spotify:image:img123",
            "album_disc_count": "1",
        },
    }
    track = TrackInfo.from_payload(payload)
    assert track.title == "Full Track"
    assert track.duration_seconds == 200.0
    assert track.is_explicit is True
    assert track.is_local is False
    assert track.has_lyrics is True
    assert track.popularity == 90
    assert track.album is not None
    assert track.album.name == "Test Album"
    assert track.album.disc_count == 1
    assert track.images.small == "https://i.scdn.co/image/small123"
    assert track.images.standard == "https://i.scdn.co/image/img123"
    assert track.url == "https://open.spotify.com/track/xyz"
    assert "Full Track by A1" in str(track)


def test_track_info_from_payload_minimal():
    """Test parsing a minimal TrackInfo payload where optional fields are missing."""
    payload = {
        "uri": "spotify:track:min",
        "name": "Minimal Track",
        "duration": 180000,
        "artists": [],
    }
    track = TrackInfo.from_payload(payload)
    assert track.title == "Minimal Track"
    assert track.album is None
    assert track.has_lyrics is None
    assert track.popularity is None
    assert track.image_url is None


def test_playback_context_parsing():
    """Test parsing PlaybackContext payload."""
    payload = {
        "uri": "spotify:playlist:123",
        "url": "context://spotify:playlist:123",
        "metadata": {
            "context_description": "My Favorite Playlist",
            "context_owner": "user_abc",
            "image_url": "spotify:image:playlist_cover",
            "playlist_number_of_tracks": "15",
        },
    }
    ctx = PlaybackContext.from_payload(payload)
    assert ctx is not None
    assert ctx.uri == "spotify:playlist:123"
    assert ctx.description == "My Favorite Playlist"
    assert ctx.owner == "user_abc"
    assert ctx.track_count == 15
    assert ctx.image_url == "https://i.scdn.co/image/playlist_cover"

    assert PlaybackContext.from_payload({}) is None


def test_playback_restrictions_parsing():
    """Test parsing PlaybackRestrictions payload."""
    payload = {
        "canPause": True,
        "canResume": False,
        "canSeek": True,
        "canSkipPrevious": True,
        "canSkipNext": False,
    }
    restr = PlaybackRestrictions.from_payload(payload)
    assert restr.can_pause is True
    assert restr.can_resume is False
    assert restr.can_seek is True
    assert restr.can_skip_next is False

    # Defaults when empty
    default_restr = PlaybackRestrictions.from_payload({})
    assert default_restr.can_pause is True


def test_player_state_parsing_full():
    """Test parsing full PlayerState snapshot."""
    payload = {
        "isPlaying": True,
        "isMuted": False,
        "volume": 0.75,
        "playerState": {
            "positionAsOfTimestamp": 10000,
            "duration": 200000,
            "shuffle": True,
            "smartShuffle": False,
            "repeat": 1,
            "timestamp": 1785633863030,
            "hasContext": True,
            "isBuffering": False,
            "index": {"itemIndex": 3},
            "restrictions": {"canSeek": True},
            "context": {
                "uri": "spotify:playlist:123",
                "metadata": {"context_description": "Rock Playlist"},
            },
            "item": {
                "name": "Active Song",
                "uri": "spotify:track:1",
                "duration": 200000,
                "artists": [{"name": "Artist 1", "uri": "spotify:artist:1"}],
            },
            "previousItems": [{"name": "Prev Song", "uri": "spotify:track:0"}],
            "nextItems": [{"name": "Next Song", "uri": "spotify:track:2"}],
        },
    }

    state = PlayerState.from_payload(payload, event_name="SongChanged")
    assert state.event_name == "SongChanged"
    assert state.is_playing is True
    assert state.volume == 75.0
    assert state.position_seconds == 10.0
    assert state.duration_seconds == 200.0
    assert state.repeat_mode == RepeatMode.CONTEXT
    assert state.item_index == 3
    assert state.track is not None
    assert state.track.title == "Active Song"
    assert state.context is not None
    assert state.context.description == "Rock Playlist"
    assert len(state.previous_tracks) == 1
    assert state.previous_tracks[0].title == "Prev Song"
    assert len(state.next_tracks) == 1
    assert state.next_tracks[0].title == "Next Song"


def test_player_state_minimal_and_edge_cases():
    """Test parsing PlayerState when empty or minimal."""
    state_empty = PlayerState.from_payload({})
    assert state_empty.is_playing is False
    assert state_empty.track is None
    assert state_empty.context is None
    assert state_empty.item_index is None


def test_requests_serialization():
    """Test serialization of request objects to Spicetify wire format."""
    set_vol = _SetVolumeRequest(level=0.5, token="test-token")
    vol_data = set_vol.model_dump(exclude_none=True)
    assert vol_data["requestName"] == "SetVolume"
    assert "requestId" in vol_data
    assert vol_data["payload"]["level"] == 0.5
    assert vol_data["token"] == "test-token"

    ping_req = _PingRequest(token="auth-key")
    ping_data = ping_req.model_dump(exclude_none=True)
    assert ping_data["requestName"] == "Ping"
    assert ping_data["payload"] == {}
    assert ping_data["token"] == "auth-key"
