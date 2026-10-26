import pytest
from unittest.mock import MagicMock, patch
from db.wards import get_ward_by_id, ward_exists


def test_get_ward_by_id_none_on_empty():
    assert get_ward_by_id("") is None
    assert get_ward_by_id(None) is None
    assert ward_exists("") is False
    assert ward_exists(None) is False


def test_get_ward_by_id_handles_missing_record_safely():
    mock_sb = MagicMock()
    # Simulate PostgREST empty list for nonexistent ward
    mock_sb.table().select().eq().limit().execute.return_value = MagicMock(data=[])

    with patch("db.wards.get_supabase", return_value=mock_sb):
        res = get_ward_by_id("nonexistent_ward_999")
        assert res is None
        assert ward_exists("nonexistent_ward_999") is False


def test_get_ward_by_id_returns_data_for_existing_ward():
    fake_ward = {
        "id": "1",
        "name": "Kempegowda Ward",
        "constituency": "Yelahanka",
        "population_density": 12500.0,
    }
    mock_sb = MagicMock()
    mock_sb.table().select().eq().limit().execute.return_value = MagicMock(data=[fake_ward])

    with patch("db.wards.get_supabase", return_value=mock_sb):
        res = get_ward_by_id("1")
        assert res == fake_ward
        assert ward_exists("1") is True


def test_get_ward_by_id_raises_on_real_db_failure():
    mock_sb = MagicMock()
    mock_sb.table().select().eq().limit().execute.side_effect = ConnectionError("Supabase connection timeout")

    with patch("db.wards.get_supabase", return_value=mock_sb):
        with pytest.raises(ConnectionError):
            get_ward_by_id("1")
