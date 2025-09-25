"""Authentication helpers for the Benchwrap CLI."""

from __future__ import annotations

import click
import requests

from .cli_constants import BASE_URL, DATA_DIR, TOK_FILE


def ensure_data_dir() -> None:
    """Make sure the data directory and token file exist with secure permissions."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not TOK_FILE.exists():
        TOK_FILE.touch(mode=0o600)


def register() -> str | bool:
    """Register a new user account and return the fresh access token."""
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
    """Return True if a refresh token is present."""
    return TOK_FILE.exists() and TOK_FILE.read_text().strip() != ""


def get_access_token() -> str | bool:
    """Refresh an access token using the stored refresh token."""
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
    """Authenticate with username/password and return the access token."""
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
