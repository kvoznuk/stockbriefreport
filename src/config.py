"""Loads config.yaml and exposes typed access to the user's fixed parameters."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Config:
    raw: dict[str, Any]

    @property
    def account_size(self) -> float:
        return float(self.raw["account"]["size_usd"])

    @property
    def max_risk_pct(self) -> float:
        return float(self.raw["account"]["max_risk_per_trade_pct"]) / 100.0

    @property
    def max_risk_dollars(self) -> float:
        return self.account_size * self.max_risk_pct

    @property
    def primary_watchlist(self) -> list[str]:
        return list(self.raw["watchlist"]["primary"])

    @property
    def expanded_watchlist(self) -> list[str]:
        return list(self.raw["watchlist"]["expanded"])

    @property
    def enabled_setups(self) -> list[str]:
        return list(self.raw["setups"]["enabled"])

    @property
    def setup_rules(self) -> dict[str, Any]:
        return dict(self.raw["setups"]["rules"])

    @property
    def csp_target_delta(self) -> float:
        return float(self.raw["wheel"]["csp_target_delta"])

    @property
    def vix_min_for_premium(self) -> float:
        return float(self.raw["wheel"]["vix_min_for_premium_selling"])

    @property
    def claude_model(self) -> str:
        return str(self.raw["claude"]["model"])

    @property
    def claude_max_tokens(self) -> int:
        return int(self.raw["claude"]["max_tokens"])

    @property
    def html_path(self) -> str:
        return str(self.raw["output"]["html_path"])

    @property
    def archive_dir(self) -> str:
        return str(self.raw["output"]["archive_dir"])


def load_config(path: str | Path = "config.yaml") -> Config:
    with open(path, "r") as f:
        return Config(raw=yaml.safe_load(f))


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


def optional_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)
