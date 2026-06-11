"""
Persist user preferences (watchlist, etc.).

Local:  reads/writes user_data.json in the project root.
Cloud:  reads/writes a GitHub Gist when GIST_ID + GITHUB_TOKEN are set.

The two env vars are optional — if absent the file backend is used.
"""

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

_LOCAL_PATH = os.path.join(os.path.dirname(__file__), "user_data.json")
_GIST_FILE  = "nse_user_data.json"
_DEFAULTS   = {"watchlist": ["RELIANCE", "TCS", "HDFCBANK", "WIPRO"]}


def _secret(key: str) -> str:
    val = os.getenv(key, "")
    if not val:
        try:
            import streamlit as st
            val = st.secrets.get(key, "")
        except Exception:
            pass
    return val


def _gist_id()   -> str: return _secret("GIST_ID")
def _gh_token()  -> str: return _secret("GITHUB_TOKEN")
def _use_gist()  -> bool: return bool(_gist_id() and _gh_token())


# ── Gist backend ──────────────────────────────────────────────────────────────

def _gist_headers() -> dict:
    return {
        "Authorization": f"token {_gh_token()}",
        "Accept": "application/vnd.github+json",
    }


def _gist_load() -> dict:
    r = requests.get(
        f"https://api.github.com/gists/{_gist_id()}",
        headers=_gist_headers(), timeout=6,
    )
    r.raise_for_status()
    content = r.json()["files"][_GIST_FILE]["content"]
    return json.loads(content)


def _gist_save(data: dict) -> None:
    requests.patch(
        f"https://api.github.com/gists/{_gist_id()}",
        headers=_gist_headers(), timeout=6,
        json={"files": {_GIST_FILE: {"content": json.dumps(data, indent=2)}}},
    )


# ── File backend ──────────────────────────────────────────────────────────────

def _file_load() -> dict:
    try:
        with open(_LOCAL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _file_save(data: dict) -> None:
    with open(_LOCAL_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Public API ────────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        data = _gist_load() if _use_gist() else _file_load()
    except Exception:
        data = {}
    for k, v in _DEFAULTS.items():
        data.setdefault(k, v)
    return data


def _save(data: dict) -> None:
    try:
        _gist_save(data) if _use_gist() else _file_save(data)
    except Exception:
        pass


def load_watchlist() -> list[str]:
    return _load()["watchlist"]


def save_watchlist(symbols: list[str]) -> None:
    data = _load()
    data["watchlist"] = list(symbols)
    _save(data)
