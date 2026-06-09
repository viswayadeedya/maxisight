import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

from maxisight._consts import MY_GREENHOUSE_SIGN_IN_URL, SESSION_DIR
from maxisight.errors import AuthError


class GreenhouseAuth:
    def __init__(self, session_dir: Path = Path(SESSION_DIR)) -> None:
        self._session_file = session_dir / "greenhouse.json"

    def login(self) -> None:
        asyncio.run(self._login())

    async def _login(self) -> None:
        self._session_file.parent.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(MY_GREENHOUSE_SIGN_IN_URL)

            # Wait until the user completes login (URL leaves the sign-in page)
            await page.wait_for_url(
                lambda url: "sign_in" not in url and "sign_up" not in url,
                timeout=300_000,  # 5 minutes for user to complete login
            )

            cookies = await context.cookies()
            await browser.close()

        if not cookies:
            raise AuthError("No cookies captured after login. Please try again.")

        session = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "cookies": cookies,
        }
        self._session_file.write_text(json.dumps(session, indent=2))

    def load_cookies(self) -> list[dict]:
        if not self._session_file.exists():
            raise AuthError(
                "No Greenhouse session found. Run 'maxisight auth greenhouse' first."
            )
        session = json.loads(self._session_file.read_text())
        return session["cookies"]

    @property
    def session_file(self) -> Path:
        return self._session_file
