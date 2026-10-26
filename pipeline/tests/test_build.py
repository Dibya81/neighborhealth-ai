from datetime import date, timedelta

import pandas as pd

from pipeline.build.reconcile import reconcile
from pipeline.build.series import _remove_monotonic_violations, build_weekly
from pipeline.extract.schema import AreaRow, Bulletin, Counts


def _row(cum: int, day: int = 0) -> AreaRow:
    return AreaRow(area="BBMP", on_day=Counts(samples=day * 2, igm=day, ns1=0, total_pos=day),
                   cumulative=Counts(samples=cum * 2, igm=cum, ns1=0, total_pos=cum))


def test_monotonic_cleaning_removes_typo():
    vals = [10, 12, 15, 150, 18, 20, 25]  # 150 is a typo (extra digit)
    keep = _remove_monotonic_violations(vals)
    assert keep == [True, True, True, False, True, True, True]


def test_weekly_series_with_gaps_outlier_and_year_reset():
    records = []
    d, cum, year = date(2023, 12, 1), 900, 2023
    while d <= date(2024, 1, 31):
        if d.year != year:          # bulletin cumulative resets on 1 January
            year, cum = d.year, 0
        cum += 5                    # 5 new cases every day
        if d.weekday() != 6:        # no bulletin on Sundays (gaps)
            value = cum * 10 if d == date(2024, 1, 10) else cum   # one typo
            records.append({"date": pd.Timestamp(d), "area": "BBMP", "trusted": True,
                            "cum_total_pos": value, "day_total_pos": 5})
        d += timedelta(days=1)
    weekly, report = build_weekly(pd.DataFrame(records), "BBMP")
    assert report["n_removed_outliers"] == 1
    inner = weekly.iloc[1:-1]       # ignore partial first/last weeks
    assert ((inner["cases"] - 35).abs() <= 6).all(), inner["cases"].tolist()


def test_reconcile_prefers_validated_candidate():
    good = Bulletin(report_date=date(2024, 7, 8), extractor="llm", rows=[_row(2083, 95)])
    bad_row = _row(2083, 95)
    bad_row.cumulative.igm = 1   # IgM + NS1 != Total -> fails validation
    bad = Bulletin(report_date=date(2024, 7, 8), extractor="rule", rows=[bad_row])
    df = reconcile({"2024-07-08": {"rule": bad, "llm": good}}, ["BBMP"], prefer="rule")
    r = df.iloc[0]
    assert r["extractor"] == "llm" and bool(r["trusted"])


def test_reconcile_flags_disagreement():
    a = Bulletin(report_date=date(2024, 7, 8), extractor="rule", rows=[_row(2083)])
    b = Bulletin(report_date=date(2024, 7, 8), extractor="llm", rows=[_row(2038)])
    df = reconcile({"2024-07-08": {"rule": a, "llm": b}}, ["BBMP"], prefer="rule")
    assert "extractors_disagree" in df.iloc[0]["flags"]
    assert df.iloc[0]["cum_total_pos"] == 2083


def test_a_week_after_the_last_real_bulletin_is_not_reported():
    """The last Sunday after the final bulletin would carry the cumulative forward and read as ~0 cases."""
    records, d, cum = [], date(2024, 10, 1), 1000
    while d <= date(2024, 11, 4):                    # last bulletin on Monday 4 Nov 2024
        cum += 10
        if d.weekday() != 6:
            records.append({"date": pd.Timestamp(d), "area": "BBMP", "trusted": True,
                            "cum_total_pos": cum, "day_total_pos": 10, "cum_year": 2024})
        d += timedelta(days=1)
    weekly, _ = build_weekly(pd.DataFrame(records), "BBMP")
    assert weekly["week_end"].max() == pd.Timestamp("2024-11-03")   # 10 Nov would be a week with no bulletins
    assert (weekly["cases"] > 50).all()                              # and no spurious near-zero week
