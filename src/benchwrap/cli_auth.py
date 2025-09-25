"""Authentication helpers for the Benchwrap CLI."""

from __future__ import annotations

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
    TOK_FILE.write_text(data["refresh"])
    click.echo("✔ Registration successful.")
    return data["access"]


def registered() -> bool:
    """Check whether a refresh token has already been stored.

    Input: none.
    Output: ``True`` when ``TOK_FILE`` exists and is non-empty, otherwise ``False``.
    """
    return TOK_FILE.exists() and TOK_FILE.read_text().strip() != ""


def get_access_token() -> str | bool:
    """Exchange the stored refresh token for a fresh access token.

    Input: relies on ``TOK_FILE`` containing a refresh token string.
    Output: new access token string or ``False`` if refresh fails.
    """
    if not TOK_FILE.exists():
        click.echo("No registration found. Please register first.")
        return False

    refresh_id = TOK_FILE.read_text().strip()
    response = requests.post(
        f"{BASE_URL}/auth/refresh",
        params={"rid": refresh_id},
        timeout=(10, 30),
    )
    if response.status_code != 200:
        click.echo(f"Token refresh failed: {response.text}")
        return False

    data = response.json()
    TOK_FILE.write_text(data["refresh"])
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
    TOK_FILE.write_text(data["refresh"])
    click.echo("✔ Login successful.")
    return data["access"]
