from __future__ import annotations

import subprocess
import sys
from typing import Any, Dict

from hatchling.builders.hooks.plugin.interface import (  # type: ignore
    BuildHookInterface,  # type: ignore
)

# info logs get swallowed by hatch, so we use this to print them

DEBUG = False


def _print(message: str) -> None:
    sys.stdout.write(message + "\n")


def _error(message: str) -> None:
    sys.stderr.write(message + "\n")


class FrontendBuildHook(BuildHookInterface):  # type: ignore
    def initialize(self, version: str, build_data: Dict[str, Any]) -> None:
        _print(str(build_data))

        _print("Starting frontend build process. This may take a minute...")
        try:
            self._check_binary("node", "Node.js")
            self._check_binary("pnpm", "pnpm")
            self._run_frontend_build()
        except Exception as e:
            _error(f"Frontend build failed: {e}")
            raise

        _print("Frontend build completed successfully")
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
            capture_output = False
            result = subprocess.run(
                ["make", "fe"],
                check=True,
                capture_output=capture_output,
                text=True,
                cwd=self.root,
            )
            if DEBUG:
                _print(f"Build output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            _error(f"Build script stderr: {e.stderr}")
            raise RuntimeError("Frontend build script failed") from e

    def clean(self, versions: list[str]) -> None:
        """Clean up build artifacts"""
        _print("Cleaning frontend build artifacts...")
        # Add any frontend cleanup logic here if needed
        super().clean(versions)
