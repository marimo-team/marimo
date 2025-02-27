from __future__ import annotations

import os
import subprocess
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBuildHook(BuildHookInterface[Any]):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        # Only build frontend if MARIMO_BUILD_FRONTEND variable exists
        MARIMO_BUILD_FRONTEND = os.getenv("MARIMO_BUILD_FRONTEND")
        if not MARIMO_BUILD_FRONTEND:
            self.app.display_debug(
                "MARIMO_BUILD_FRONTEND is not set, skipping frontend build"
            )
            return

        self.app.display_info(f"Build data: {str(build_data)}")
        self.app.display_info(f"Project root: {self.root}")
        self.app.display_info(f"Build dir: {self.directory}")

        self.app.display_info(
            "Starting frontend build process. This may take a minute..."
        )
        try:
            self._check_binary("node", "Node.js")
            self._check_binary("pnpm", "pnpm")
            self._run_frontend_build()
        except Exception as e:
            self.app.display_error(f"Frontend build failed: {e}")
            raise

        self.app.display_info("Frontend build completed successfully")
        return super().initialize(version, build_data)

    def _check_binary(self, binary: str, display_name: str) -> None:
        try:
            subprocess.run(
                [binary, "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"{display_name} is not installed. Please install {display_name} and try again."
            ) from None
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"{display_name} check failed: {e.stderr}"
            ) from None

    def _run_frontend_build(self) -> None:
        try:
            # Uncomment to hide output
            capture_output = True
            result = subprocess.run(
                ["make", "fe"],
                check=True,
                capture_output=capture_output,
                text=True,
                cwd=self.root,
            )
            if capture_output:
                self.app.display_debug(f"Build output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            self.app.display_error(f"Build script stderr: {e.stderr}")
            raise RuntimeError("Frontend build script failed") from e

    def clean(self, versions: list[str]) -> None:
        """Clean up build artifacts"""
        self.app.display_info("Cleaning frontend build artifacts...")
        # Add any frontend cleanup logic here if needed
        super().clean(versions)
