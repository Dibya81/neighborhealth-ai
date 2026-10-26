# Data card: NeighborHealth 2.0

## Target: BBMP weekly reported dengue cases
* **Source:** Karnataka State NVBDCP, *Daily Report of Dengue in Karnataka State*, as archived by the
  International Centre for Theoretical Sciences (ICTS), Bengaluru: `extranet.icts.res.in/Dengue/Data-repository/`.
  Please cite both NVBDCP Karnataka and the ICTS archive in anything you publish.
* **Unit:** lab-confirmed positives (IgM MAC ELISA + NS1 antigen) reported for Bruhat Bengaluru
  Mahanagara Palike (BBMP), aggregated to weeks ending Sunday.
* **Construction:** weekly cases = difference of the year-to-date cumulative count between consecutive
  Sundays (daily values linearly interpolated over missing bulletin days). Each week records how many
  real bulletins it contains (`n_obs`) and a `quality` label.
* **Not included:** suspected-but-untested cases, most private-lab results, unreported infections.
  Testing volume changes over time, so case counts partly reflect testing effort (we keep `cum_samples`
  so models can account for this).

## What the real archive actually contains (measured 2026-10-26)
* **Coverage:** 606 bulletins, 2021-09-29 to **2024-11-04**. The archive has nothing earlier and nothing after
  that date, so every forecast in this repo is built from data that is now roughly two years old.
  `/health` reports this honestly, and the alert engine refuses to run on a forecast older than 21 days.
* **Two file types:** text PDFs (to about Sep 2023) are parsed by column position; **165 scans** (Oct 2023 on) are
  read by OCR (Apple Vision, macOS only) for the BBMP and state-total rows only, accepting a reading only when
  IgM + NS1 = Total and Total <= Samples <= Suspected. OCR output is committed
  (`data/v2/interim/extracted_rule.jsonl`) so other machines do not need to repeat it.
* **Gaps:** many dates have no bulletin (weekends, holidays) and Apr-May 2023 is missing entirely (7 weeks, interpolated and
  flagged `interpolated`). Of 162 weeks, 113 have 3 or more real observations (`quality == "ok"`). Forecast
  backtests are scored **only on those weeks**, never on interpolated values.
* **Accuracy checks that need no hand labels:**
  * 374 of 379 text bulletins: the district rows sum exactly to the printed state total.
  * Against the Ministry's separate annual table (NCVBDC, "Dengue cases and deaths 2021-2026"), Karnataka
    totals rebuilt from the bulletins (state total + BBMP) are 100% (2021), 98% (2022) and 95% (2024, through 4 Nov) of
    the official figure. **2023 is 87%**: the daily bulletins end below the official annual number
    (smooth series, not an OCR error), so treat 2023 weekly counts as a lower bound.
  * 129 of 165 scanned bulletins yielded a BBMP value; most of the rest are genuinely blank rows. I checked 4 scans against the images by eye.
* **Anomalies kept out:** some bulletins print daily counts in the cumulative columns (e.g. BBMP 415 where neighbours show
  24,000+) or repeat a stale day. The series builder drops points that break monotonicity within a year.

## Features: weather
* NASA POWER daily point data at the city centre (MERRA-2 based reanalysis): T2M, T2M_MAX, T2M_MIN, RH2M,
  PRECTOTCORR. Aggregated weekly (rain sum, rainy days ≥ 2.5 mm, mean temperatures and humidity).
* One point for the whole city: no intra-city variation.

## Geography
* Ward polygons: 243 wards (2023 delimitation). Census 2011 demographics: 198 wards (2011 delimitation).
  The two do not line up 1:1; a spatial crosswalk (area-weighted overlay) is required and is part of Step 2.

## Known limitations
* District-level surveillance only: any ward-level number in the app is a *model estimate* with
  uncertainty, never an observed count.
* Extraction errors are possible; see `docs/v2/extraction_eval.md` for measured accuracy.
* v1's `spatiotemporal_training_matrix.csv` and `dengue_karnataka.csv` are synthetic and are **not** used in v2
  (and are not committed). Only real inputs are tracked: NASA POWER weather, Census 2011 ward table, ward polygons.
* Source for validation: NCVBDC, `Doc/Dengue-Cases-deaths-2021-2026-till-April.pdf` (annual state totals; Karnataka 2025: 7,325).
