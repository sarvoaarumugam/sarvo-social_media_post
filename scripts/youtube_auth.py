"""One-time YouTube OAuth setup.

Run this ONCE:
    uv run python scripts/youtube_auth.py

A browser window opens -> log in with the Google account that owns your channel ->
click Allow. That saves token.json, and from then on every upload is unattended.

(If you ever see 'access blocked', make sure your email is added as a Test user on
the OAuth consent screen in Google Cloud Console.)
"""

from pathlib import Path

from app.core.config import get_settings
from app.services.youtube_uploader import get_credentials


def main() -> None:
    settings = get_settings()
    if not Path(settings.youtube_client_secret_file).exists():
        raise SystemExit(f"Missing {settings.youtube_client_secret_file} in the project root.")

    print("Opening browser for Google login (one time only)...")
    creds = get_credentials()
    print("-" * 50)
    print(f"Success! Token saved to {settings.youtube_token_file}")
    print(f"Valid: {creds.valid} | has refresh token: {bool(creds.refresh_token)}")
    print("All future uploads will run unattended.")


if __name__ == "__main__":
    main()
