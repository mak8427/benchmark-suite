"""Authentication helpers for the Benchwrap CLI."""

from __future__ import annotations

import base64
import json

import click
import requests

from .cli_constants import BASE_URL, DATA_DIR, TOK_FILE


def ensure_data_dir() -> None:
    """Create the data directory and token file if needed.

    Input: none.
    Output: ensures ``DATA_DIR`` exists and ``TOK_FILE`` is present with 0600 perms.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not TOK_FILE.exists():
        TOK_FILE.touch(mode=0o600)


def _decode_access_payload(access_token: str) -> dict[str, str]:
    """Decode JWT payload without verifying it, for local display/state only."""
    try:
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = base64.urlsafe_b64decode(payload.encode("ascii"))
        decoded = json.loads(data.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _read_token_state() -> dict[str, str]:
    """Read token state, accepting the legacy plain-refresh-token format."""
    if not TOK_FILE.exists():
        return {}
    raw = TOK_FILE.read_text().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"refresh": raw}
    return data if isinstance(data, dict) else {}


def _write_token_state(*, refresh: str, username: str | None = None) -> None:
    """Persist the active account credentials."""
    ensure_data_dir()
    state = {"refresh": refresh}
    if username:
        state["username"] = username
    TOK_FILE.write_text(json.dumps(state, sort_keys=True))


def active_username() -> str | None:
    """Return the locally stored active username when known."""
    value = _read_token_state().get("username")
    return str(value) if value else None


def register() -> str | bool:
    """Register a new account and capture the returned access token.

    Input: prompts interactively for username/password details.
    Output: access token string on success, ``False`` when registration fails.
    """
    ensure_data_dir()

    username = click.prompt("Username", type=str)
    password = click.prompt("Password", hide_input=True)
    if password != click.prompt("Re-enter Password", hide_input=True):
        click.echo("Passwords do not match!")
        return False

    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={"username": username, "password": password},
        timeout=(10, 30),
    )
    if response.status_code != 201:
        click.echo(f"Registration failed: {response.text}")
        return False

    data = response.json()
    _write_token_state(refresh=data["refresh"], username=username)
    click.echo("✔ Registration successful.")
    return data["access"]


def registered() -> bool:
    """Check whether a refresh token has already been stored.

    Input: none.
    Output: ``True`` when ``TOK_FILE`` exists and is non-empty, otherwise ``False``.
    """
    return bool(_read_token_state().get("refresh"))


def get_access_token() -> str | bool:
    """Exchange the stored refresh token for a fresh access token.

    Input: relies on ``TOK_FILE`` containing a refresh token string.
    Output: new access token string or ``False`` if refresh fails.
    """
    if not TOK_FILE.exists():
        click.echo("No registration found. Please register first.")
        return False

    token_state = _read_token_state()
    refresh_id = token_state.get("refresh", "")
    response = requests.post(
        f"{BASE_URL}/auth/refresh",
        params={"rid": refresh_id},
        timeout=(10, 30),
    )
    if response.status_code != 200:
        click.echo(f"Token refresh failed: {response.text}")
        return False

    data = response.json()
    payload = _decode_access_payload(data.get("access", ""))
    username = token_state.get("username") or payload.get("username")
    _write_token_state(refresh=data["refresh"], username=username)
    return data["access"]


def login() -> str | bool:
    """Authenticate via username/password and persist the refresh token.

    Input: prompts interactively for credentials.
    Output: access token string on success, ``False`` when authentication fails.
    """
    ensure_data_dir()

    username = click.prompt("Username", type=str)
    password = click.prompt("Password", hide_input=True)
    response = requests.post(
        f"{BASE_URL}/auth/password",
        params={"u": username, "p": password},
        timeout=(10, 30),
    )
    if response.status_code != 200:
        click.echo(f"Login failed: {response.text}")
        return False

    data = response.json()
    _write_token_state(refresh=data["refresh"], username=username)
    click.echo("✔ Login successful.")
    return data["access"]


@click.command()
def logout() -> None:
    """Clear the active account credentials without deleting sync history."""
    ensure_data_dir()
    if TOK_FILE.exists():
        TOK_FILE.write_text("")
    click.echo("✔ Logged out.")
