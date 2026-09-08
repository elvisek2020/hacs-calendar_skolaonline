"""Asynchronní klient neoficiálního API Škola OnLine."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.util import dt as dt_util

from .const import API_BASE_URL, API_CLIENT_ID, API_SCOPE

_LOGGER = logging.getLogger(__name__)

# Token se obnoví s rezervou, aby request nespadl na hraně platnosti.
TOKEN_REFRESH_MARGIN = timedelta(seconds=60)
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class SkolaOnlineError(Exception):
    """Obecná chyba komunikace se Škola OnLine."""


class SkolaOnlineAuthError(SkolaOnlineError):
    """Přihlášení bylo odmítnuto nebo vypršelo."""


class SkolaOnlineClient:
    """Klient nad REST API Škola OnLine."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        base_url: str = API_BASE_URL,
    ) -> None:
        """Inicializuje klienta bez jakéhokoli síťového volání."""
        self._session = session
        self._username = username
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def base_url(self) -> str:
        """Vrátí základní URL API."""
        return self._base_url

    async def _fetch_token(self, payload: dict[str, str]) -> None:
        """Zavolá token endpoint a uloží získané tokeny."""
        url = f"{self._base_url}/connect/token"
        try:
            response = await self._session.post(
                url, data=payload, timeout=REQUEST_TIMEOUT
            )
            body = await response.json(content_type=None)
        except aiohttp.ClientError as err:
            raise SkolaOnlineError(f"Nepodařilo se spojit s API: {err}") from err
        except ValueError as err:
            raise SkolaOnlineError("Token endpoint nevrátil JSON") from err

        if response.status in (400, 401):
            # Špatné heslo i neplatný refresh token vrací 400 s error popisem.
            raise SkolaOnlineAuthError(
                f"Přihlášení odmítnuto: {body.get('error', response.status)}"
            )
        if response.status != 200:
            raise SkolaOnlineError(f"Token endpoint vrátil HTTP {response.status}")

        access_token = body.get("access_token")
        if not access_token:
            raise SkolaOnlineError("Odpověď neobsahuje access_token")

        self._access_token = access_token
        self._refresh_token = body.get("refresh_token") or self._refresh_token
        expires_in = int(body.get("expires_in") or 3600)
        self._token_expires_at = dt_util.utcnow() + timedelta(seconds=expires_in)

    async def async_login(self) -> None:
        """Přihlásí se jménem a heslem (password grant)."""
        await self._fetch_token(
            {
                "grant_type": "password",
                "client_id": API_CLIENT_ID,
                "username": self._username,
                "password": self._password,
                "scope": API_SCOPE,
            }
        )

    async def _async_ensure_token(self) -> None:
        """Zajistí platný access token, případně ho obnoví."""
        if (
            self._access_token is not None
            and self._token_expires_at is not None
            and dt_util.utcnow() + TOKEN_REFRESH_MARGIN < self._token_expires_at
        ):
            return

        if self._refresh_token:
            try:
                await self._fetch_token(
                    {
                        "grant_type": "refresh_token",
                        "client_id": API_CLIENT_ID,
                        "refresh_token": self._refresh_token,
                    }
                )
                return
            except SkolaOnlineAuthError:
                _LOGGER.debug("Refresh token neplatný, přihlašuji se znovu heslem")
                self._refresh_token = None

        await self.async_login()

    async def _async_get(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Provede autentizovaný GET požadavek."""
        await self._async_ensure_token()

        url = f"{self._base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            response = await self._session.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            )
            if response.status == 401:
                # Token mohl být zneplatněn na serveru; jeden pokus o obnovu.
                self._access_token = None
                await self._async_ensure_token()
                headers = {"Authorization": f"Bearer {self._access_token}"}
                response = await self._session.get(
                    url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
                )

            if response.status == 401:
                raise SkolaOnlineAuthError("API odmítlo token i po obnovení")
            if response.status != 200:
                raise SkolaOnlineError(f"{endpoint} vrátil HTTP {response.status}")

            return await response.json(content_type=None)
        except aiohttp.ClientError as err:
            raise SkolaOnlineError(f"Chyba požadavku na {endpoint}: {err}") from err
        except ValueError as err:
            raise SkolaOnlineError(f"{endpoint} nevrátil JSON") from err

    async def async_get_user(self) -> dict[str, Any]:
        """Vrátí informace o přihlášeném uživateli."""
        return await self._async_get("/v1/user")

    async def async_get_timetable(
        self, student_id: str, date_from: date, date_to: date
    ) -> dict[str, Any]:
        """Vrátí rozvrh studenta v zadaném rozsahu dat."""
        return await self._async_get(
            "/v1/timeTable",
            {
                "StudentId": student_id,
                "DateFrom": date_from.isoformat(),
                "DateTo": date_to.isoformat(),
            },
        )
