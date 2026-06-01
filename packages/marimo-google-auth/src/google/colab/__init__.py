"""``google.colab`` namespace, marimo-flavored.

Importing this package installs the ``pydata_google_auth`` patch as a
side-effect (when ``pydata_google_auth`` is installed). The patch is
the whole point: it makes every library that uses ``pydata-google-auth``
(``gdrive-fsspec``, ``pandas-gbq``, …) pick up our auth bridge
automatically.

The side-effect can be disabled by setting
``MARIMO_GOOGLE_AUTH_NO_AUTO_PATCH=1`` in the environment before import.
"""

from __future__ import annotations

import logging
import os

LOGGER = logging.getLogger(__name__)


def _maybe_auto_install_patch() -> None:
    if os.environ.get("MARIMO_GOOGLE_AUTH_NO_AUTO_PATCH"):
        LOGGER.debug("MARIMO_GOOGLE_AUTH_NO_AUTO_PATCH set; skipping auto-patch.")
        return
    try:
        from google.colab import _patch

        _patch.install_pydata_patch()
    except Exception as e:
        # Never block ``import google.colab`` on patch failure — code
        # that only uses ``authenticate_user`` directly should still work.
        LOGGER.warning(
            "marimo-google-auth: failed to auto-install pydata patch: %s",
            e,
        )


_maybe_auto_install_patch()
