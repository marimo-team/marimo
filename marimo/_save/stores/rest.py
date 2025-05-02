# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import urllib.error
import urllib.request
from typing import Optional

from marimo._save.stores.store import Store


class RestStore(Store):
    def __init__(
        self, base_url: str, api_key: str, project_id: Optional[str] = None
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
                    return response.read()  # type: ignore[no-any-return]
        except urllib.error.HTTPError:
            pass
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
            urllib.request.urlopen(req)
        except urllib.error.HTTPError:
            pass

    def hit(self, key: str) -> bool:
        url = self._get_url(key)
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            method="HEAD",
        )
        try:
            with urllib.request.urlopen(req) as response:
                return response.status == 200  # type: ignore[no-any-return]
        except urllib.error.HTTPError:
            return False

    def _get_url(self, key: str) -> str:
        url = self.base_url
        if self.project_id:
            url = f"{url}/{self.project_id}"
        return f"{url}/{key}"
