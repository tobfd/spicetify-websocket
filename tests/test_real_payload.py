"""Tests against a real ``Spicetify.Player.data`` snapshot captured from Spotify Desktop.

The fixture was recorded with spicetify-connect-api v0.3.1 on a current Spotify client,
then sanitized (session, playback and interaction IDs removed) and trimmed to two
upcoming tracks.
"""

import copy
import json
from pathlib import Path

import pytest

from spicetify import PlayerState, RepeatMode, TrackInfo
from spicetify.models import _convert_spotify_image_url

FIXTURE = Path(__file__).parent / "fixtures" / "spicetify_player_data.json"


@pytest.fixture
def player_data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _extension_payload(player_data: dict, volume: float = 0.42, hearted: bool = True) -> dict:
    """Wrap player data the same way getFullPlayerState() in the extension does."""
    progress = player_data["positionAsOfTimestamp"]
    patched = dict(
        player_data,
        position_as_of_timestamp=progress,
        positionAsOfTimestamp=progress,
        volume=volume,
        is_muted=False,
        isMuted=False,
        is_hearted=hearted,
        isHearted=hearted,
    )
    return {
        "playerData": patched,
        "isPlaying": not player_data["isPaused"],
        "volume": volume,
        "isMuted": False,
        "isHearted": hearted,
        "shuffle": player_data["shuffle"],
        "repeat": player_data["repeat"],
        "progress": progress,
    }


def test_player_state_from_real_payload(player_data: dict):
    state = PlayerState.from_payload(_extension_payload(player_data), event_name="SongChanged")

    assert state.event_name == "SongChanged"
    assert state.is_playing is True
    assert state.volume == 42.0
    assert state.repeat_mode == RepeatMode.TRACK
    assert state.shuffle is False
    assert state.position_ms == player_data["positionAsOfTimestamp"]
    assert state.duration_ms == player_data["duration"]
    assert state.is_hearted is True
    assert state.has_context is True
    assert state.item_index is None
    assert state.timestamp is not None


def test_track_metadata_from_real_payload(player_data: dict):
    state = PlayerState.from_payload(_extension_payload(player_data))
    track = state.track

    assert track is not None
    assert track.title == player_data["item"]["name"]
    assert track.uri == player_data["item"]["uri"]
    assert [a.name for a in track.artists] == [a["name"] for a in player_data["item"]["artists"]]
    assert track.album is not None
    assert track.album.name == player_data["item"]["album"]["name"]
    assert track.duration_ms == player_data["item"]["duration"]["milliseconds"]
    assert track.popularity is not None
    assert track.has_lyrics is not None
    for url in (track.images.small, track.images.standard, track.images.large, track.image_url):
        assert url is not None
        assert url.startswith("https://i.scdn.co/image/")


def test_restrictions_use_camel_case_keys(player_data: dict):
    state = PlayerState.from_payload(_extension_payload(player_data))

    # The snapshot was taken while playing, so Spotify reports "not_paused" for resuming.
    assert state.restrictions.can_resume is False
    assert state.restrictions.can_pause is True
    assert state.restrictions.can_toggle_shuffle is True


def test_context_from_real_payload(player_data: dict):
    state = PlayerState.from_payload(_extension_payload(player_data))

    assert state.context is not None
    assert state.context.uri == player_data["context"]["uri"]
    assert state.context.owner == "spotify"
    assert state.context.track_count == 1
    assert state.context.image_url is None  # Spotify sends an empty string here


def test_queue_tracks_read_liked_state_from_collection_metadata(player_data: dict):
    data = copy.deepcopy(player_data)
    data["nextItems"][1]["metadata"]["collection.in_collection"] = "false"

    state = PlayerState.from_payload(_extension_payload(data))

    assert len(state.next_tracks) == 2
    assert len(state.previous_tracks) == 1
    assert state.next_tracks[0].is_hearted is True
    assert state.next_tracks[1].is_hearted is False


def test_track_info_tolerates_null_fields():
    track = TrackInfo.from_payload(
        {"uri": None, "name": None, "artists": [{"name": None, "uri": None}], "metadata": None}
    )

    assert track.uri == ""
    assert track.title == ""
    assert track.artists[0].name == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("spotify:image:ab67", "https://i.scdn.co/image/ab67"),
        ("ab67616d00001e02", "https://i.scdn.co/image/ab67616d00001e02"),
        ("https://example.com/a.png", "https://example.com/a.png"),
        ("spotify:localfileimage:C%3A%5Cmusic%5Ccover.jpg", None),
        ("spotify:image:", None),
        ("", None),
        (None, None),
    ],
)
def test_convert_spotify_image_url(raw, expected):
    assert _convert_spotify_image_url(raw) == expected
