"""Test fixtures: small PDFs that reproduce real bulletin rows (copied from actual 2024 bulletins),
including the messy cases the parser must handle."""
from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas

# Real rows from the 08-07-2024 bulletin (BBMP row appears without its label in the PDF text).
BULLETIN_A = [
    "Daily Report of Dengue in Karnataka State - 2024",
    "Report No. NVBDCP/HS/2 (1)/2024        Date: 08 - 07 - 2024",
    "SL NO District Total No. of blocks Taluks PHC Suspected Cases",
    "2024 Igm Mac Elisa NS1 Antign Total +ves Igm Mac Elisa NS1 Antign Total +ves",
    "1 Bangaluru (U) 4 4 20 32 72498 10 4 4 0 4 0 1005 389 35 0 35 0",
    "2 Bangaluru (R) 4 4 19 25 39864 630 397 11 19 30 0",
    "1200 800 40 20 60 0",                       # cumulative split onto its own line
    "3 Ramanagar 4 4 38 56 45679 2808 761 2 58 60 0 9000 4000 100 200 300 0",
    "0 0 0 0 151 115 16 79 95 0 8675 6499 642 1441 2083 1",   # BBMP, label lost
    "176 98 877 1488 2635534 1671 600 31 13 44 0 61996 38092 1669 932 2601 0",
    "Bangaluru City (BBMP) figures are reported separately.",
    "",
    "Daily Report of Chikungunya in Karnataka State - 2024",
    "Bangaluru City (BBMP) 0 0 0 0 415 75 34 0 34 0",        # must be ignored (wrong disease)
    "1 Bangaluru (U) 4 1 6 8 16180 115 22 8 0 8 0 999 500 90 9 99 0",
]

# Real-style rows from 18-05-2024: labelled BBMP row with only on-the-day numbers.
BULLETIN_B = [
    "Daily Report of Dengue in Karnataka State - 2024",
    "Date: 18 - 05 - 2024",
    "1 Bangaluru (U) 4 1 7 9 24203 175 36 11 0 11 0 300 200 50 10 60 0",
    "Bangaluru City (BBMP) 0 0 0 0 209 201 57 0 57 0",
    "176 88 912 1435 2607525 907 208 16 26 42 0 53345 25283 1284 1193 2477 0",
]


def make_pdf(path: Path, lines: list[str]) -> Path:
    c = canvas.Canvas(str(path), pagesize=landscape(A4))
    y = 560
    for line in lines:
        c.setFont("Helvetica", 8)
        c.drawString(30, y, line)
        y -= 16
    c.save()
    return path


@pytest.fixture
def pdf_a(tmp_path):
    return make_pdf(tmp_path / "2024-07-08.pdf", BULLETIN_A)


@pytest.fixture
def pdf_b(tmp_path):
    return make_pdf(tmp_path / "2024-05-18.pdf", BULLETIN_B)
