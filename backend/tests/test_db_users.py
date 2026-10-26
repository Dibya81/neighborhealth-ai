import json
from unittest.mock import MagicMock, patch
from db.users import upsert_user


def test_upsert_user_saved_locations_native_jsonb():
    mock_sb = MagicMock()
    mock_sb.table().upsert().execute.return_value = MagicMock(data=[{"id": "user-1", "name": "Aarav"}])

    locations_list = [
        {"label": "home", "ward_id": "1", "lat": 12.9716, "lng": 77.5946},
        {"label": "office", "ward_id": "131", "lat": 12.9800, "lng": 77.6200},
    ]

    with patch("db.users.get_supabase", return_value=mock_sb):
        upsert_user(
            name="Aarav",
            email="aarav@bengaluru.in",
            saved_locations=locations_list,
        )

        # Inspect the payload sent to Supabase table('users').upsert(payload)
        call_args = mock_sb.table("users").upsert.call_args[0][0]
        assert call_args["saved_locations"] == locations_list
        # Verify it is NOT a serialized JSON string (which would be double-encoded in JSONB)
        assert not isinstance(call_args["saved_locations"], str)
        assert isinstance(call_args["saved_locations"], list)


def test_upsert_user_saved_locations_parses_json_string():
    mock_sb = MagicMock()
    mock_sb.table().upsert().execute.return_value = MagicMock(data=[{"id": "user-2", "name": "Priya"}])

    raw_json_str = '[{"label": "school", "ward_id": "50"}]'

    with patch("db.users.get_supabase", return_value=mock_sb):
        upsert_user(
            name="Priya",
            email="priya@bengaluru.in",
            saved_locations=raw_json_str,
        )

        call_args = mock_sb.table("users").upsert.call_args[0][0]
        assert isinstance(call_args["saved_locations"], list)
        assert call_args["saved_locations"][0]["label"] == "school"
