# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import urllib.error
import urllib.request
from typing import Optional

from marimo import _loggers
from marimo._save.stores.store import Store

LOGGER = _loggers.marimo_logger()


class RestStore(Store):
    def __init__(
        self, *, base_url: str, api_key: str, project_id: Optional[str] = None
    ) -> None:
        super().__init__()
        assert api_key, "api_key is required"
        assert base_url, "base_url is required"

        self.base_url = base_url
        self.api_key = api_key
        self.project_id = project_id

    def get(self, key: str) -> Optional[bytes]:
        url = self._get_url(key)
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.api_key}"}
        )
        try:
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    LOGGER.debug(f"GET {url} - Status: {response.status}")
                    return response.read()  # type: ignore[no-any-return]
        except urllib.error.HTTPError as e:
            LOGGER.warning(
                f"GET {url} - Status: {e.status} - Error: {e.reason}"
            )
        except Exception as e:
            LOGGER.warning(f"GET {url} - Error: {e}")
        return None

    def put(self, key: str, value: bytes) -> None:
        url = self._get_url(key)
        data = value
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/octet-stream",
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req) as response:
                LOGGER.debug(f"PUT {url} - Status: {response.status}")
        except urllib.error.HTTPError as e:
            LOGGER.warning(
                f"PUT {url} - Status: {e.status} - Error: {e.reason}"
            )
        except Exception as e:
            LOGGER.warning(f"PUT {url} - Error: {e}")

    def hit(self, key: str) -> bool:
        url = self._get_url(key)
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            method="HEAD",
        )
        try:
            with urllib.request.urlopen(req) as response:
                LOGGER.debug(f"HEAD {url} - Status: {response.status}")
                return response.status == 200  # type: ignore[no-any-return]
        except urllib.error.HTTPError as e:
            LOGGER.warning(
                f"HEAD {url} - Status: {e.status} - Error: {e.reason}"
            )
            return False
        except Exception as e:
            LOGGER.warning(f"HEAD {url} - Error: {e}")
            return False

    def _get_url(self, key: str) -> str:
        url = self.base_url
        if self.project_id:
            url = f"{url}/{self.project_id}"
        return f"{url}/{key}"
