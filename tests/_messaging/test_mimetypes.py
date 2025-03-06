# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, cast

from marimo._messaging.mimetypes import (
    KnownMimeType,
    MimeBundle,
    MimeBundleOrTuple,
)


class TestMimeTypes:
    def test_known_mime_type(self) -> None:
        # Test that KnownMimeType can be used as a type annotation
        def accepts_mime_type(mime_type: KnownMimeType) -> KnownMimeType:
            return mime_type

        # Test with various known mime types
        assert accepts_mime_type("text/plain") == "text/plain"
        assert accepts_mime_type("text/html") == "text/html"
        assert accepts_mime_type("application/json") == "application/json"
        assert accepts_mime_type("image/png") == "image/png"

        # The following would fail type checking but not at runtime
        # This test is just to verify the runtime behavior
        assert (
            accepts_mime_type(cast(KnownMimeType, "unknown/type"))
            == "unknown/type"
        )

    def test_mime_bundle(self) -> None:
        # Test that MimeBundle can be used as a type annotation
        def accepts_mime_bundle(bundle: MimeBundle) -> MimeBundle:
            return bundle

        # Create a valid mime bundle
        bundle: MimeBundle = {
            "text/plain": "Hello, world!",
            "text/html": "<h1>Hello, world!</h1>",
        }

        assert accepts_mime_bundle(bundle) == bundle

        # Test with empty bundle
        empty_bundle: MimeBundle = {}
        assert accepts_mime_bundle(empty_bundle) == empty_bundle

    def test_mime_bundle_or_tuple(self) -> None:
        # Test that MimeBundleOrTuple can be used as a type annotation
        def accepts_mime_bundle_or_tuple(
            bundle_or_tuple: MimeBundleOrTuple,
        ) -> MimeBundleOrTuple:
            return bundle_or_tuple

        # Test with a bundle
        bundle: MimeBundle = {"text/plain": "Hello, world!"}
        assert accepts_mime_bundle_or_tuple(bundle) == bundle

        # Test with a tuple
        metadata = {"key": "value"}
        bundle_tuple: tuple[MimeBundle, Any] = (bundle, metadata)
        assert accepts_mime_bundle_or_tuple(bundle_tuple) == bundle_tuple
