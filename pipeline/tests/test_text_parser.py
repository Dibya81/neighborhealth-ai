from datetime import date
from pathlib import Path

from pipeline.extract.text_parser import _split_tokens, interpret_numbers, parse_bulletin
from pipeline.validate.checks import check_bulletin


def test_split_tokens_drops_serial_number():
    words = [{"text": t, "x1": 10.0 * i} for i, t in enumerate("1 Bangaluru (U) 4 4 20 32 72498 10 4 4 0 4 0".split())]
    label, nums, x1s = _split_tokens(words)
    assert label == "Bangaluru (U)"
    assert nums[:3] == [4, 4, 20] and len(nums) == 11 and len(x1s) == 11


# ---- regression tests on REAL bulletins (public NVBDCP PDFs) -------------------------------
REAL = Path(__file__).parent / "real_fixtures"


def test_real_2022_cumulative_only_rows_are_not_read_as_on_day():
    """Most real rows leave 'On the day' blank; the six numbers present are CUMULATIVE."""
    b = parse_bulletin(REAL / "2022-01-03.pdf", date(2022, 1, 3))
    bbmp = b.get("BBMP")
    assert bbmp.cumulative.total_pos == 1570 and bbmp.cumulative.samples == 5950
    assert bbmp.on_day.total_pos is None
    assert b.get("Davanagere").cumulative.total_pos == 287
    assert b.get("Chitradurga").on_day.total_pos == 12 and b.get("Chitradurga").cumulative.total_pos == 241
    assert b.year_in_pdf == 2021                       # early-January 2022 files still report year 2021


def test_real_rows_sum_to_printed_state_total():
    for name, d in [("2022-01-03.pdf", date(2022, 1, 3)), ("2023-07-10.pdf", date(2023, 7, 10))]:
        b = parse_bulletin(REAL / name, d)
        districts = [r for r in b.rows if r.area not in ("STATE_TOTAL", "BBMP")]
        assert len(districts) >= 30                   # no row lost to rotated footnotes / split lines
        assert sum(r.cumulative.total_pos for r in districts) == b.get("STATE_TOTAL").cumulative.total_pos
        assert not check_bulletin(b)["_bulletin"]


def test_interpret_full_district_row():
    nums = [4, 4, 20, 32, 72498, 10, 4, 4, 0, 4, 0, 1005, 389, 35, 0, 35, 0]
    out, warnings = interpret_numbers(nums)
    assert out["blocks"] == 4 and out["population_affected"] == 72498
    assert out["on_day"].total_pos == 4
    assert out["cumulative"].total_pos == 35
    assert not warnings


def test_interpret_bbmp_row_without_blocks():
    out, _ = interpret_numbers([0, 0, 0, 0, 151, 115, 16, 79, 95, 0, 8675, 6499, 642, 1441, 2083, 1])
    assert "blocks" not in out
    assert out["on_day"].total_pos == 95
    assert out["cumulative"].total_pos == 2083 and out["cumulative"].deaths == 1


def test_parse_messy_bulletin(pdf_a):
    b = parse_bulletin(pdf_a, date(2024, 7, 8))
    bbmp = b.get("BBMP")
    assert bbmp is not None and bbmp.inferred_label
    assert bbmp.cumulative.total_pos == 2083          # from the dengue table...
    assert bbmp.on_day.total_pos == 95                # ...not the chikungunya one (34)
    assert b.get("Bengaluru Urban").cumulative.total_pos == 35
    rural = b.get("Bengaluru Rural")
    assert rural.on_day.total_pos == 30
    assert rural.cumulative.total_pos == 60          # stitched from the continuation line
    assert b.get("STATE_TOTAL").cumulative.total_pos == 2601
    assert b.year_in_pdf == 2024
    assert not any("date" in w for w in b.warnings)


def test_parse_labelled_bbmp_without_cumulative(pdf_b):
    b = parse_bulletin(pdf_b, date(2024, 5, 18))
    bbmp = b.get("BBMP")
    assert bbmp is not None and not bbmp.inferred_label
    assert bbmp.on_day.total_pos == 57
    assert bbmp.cumulative is None
    assert "cum_missing" in check_bulletin(b)["BBMP"]


def test_date_mismatch_is_flagged(pdf_b):
    b = parse_bulletin(pdf_b, date(2024, 5, 19))
    assert "date_mismatch" in check_bulletin(b)["_bulletin"]
