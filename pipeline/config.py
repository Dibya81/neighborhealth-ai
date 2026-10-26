"""Loads the city YAML config and resolves project paths."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def raw_bulletins(self) -> Path:
        return self.root / "raw" / "bulletins"

    @property
    def manifest(self) -> Path:
        return self.root / "raw" / "bulletins_manifest.csv"

    @property
    def interim(self) -> Path:
        return self.root / "interim"

    @property
    def processed(self) -> Path:
        return self.root / "processed"

    @property
    def gold(self) -> Path:
        return self.root / "gold"

    @property
    def llm_cache(self) -> Path:
        return self.root / "cache" / "llm"

    def ensure(self) -> "Paths":
        for p in (self.raw_bulletins, self.interim, self.processed, self.gold, self.llm_cache):
            p.mkdir(parents=True, exist_ok=True)
        return self


@lru_cache(maxsize=None)
def load_city(city_id: str | None = None) -> dict:
    city_id = city_id or os.environ.get("NH_CITY", "bengaluru")
    path = REPO_ROOT / "config" / "cities" / f"{city_id}.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_paths(city_id: str | None = None) -> Paths:
    override = os.environ.get("NH_DATA_ROOT")  # used by tests and deployments
    if override:
        return Paths(Path(override)).ensure()
    cfg = load_city(city_id)
    return Paths(REPO_ROOT / cfg["paths"]["data_root"]).ensure()


def canonical_area(raw_label: str, city_id: str | None = None) -> str | None:
    """Map a raw row label from a bulletin to a canonical area name using the alias table."""
    if not raw_label:
        return None
    label = " ".join(raw_label.lower().split())
    aliases = load_city(city_id)["surveillance"]["area_aliases"]
    # Check BBMP first: its labels can contain "bangaluru" too.
    for area in sorted(aliases, key=lambda a: a != "BBMP"):
        if any(alias in label for alias in aliases[area]):
            return area
    return raw_label.strip().title()
