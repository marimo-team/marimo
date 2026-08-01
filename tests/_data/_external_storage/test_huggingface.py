# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from inline_snapshot import snapshot

from marimo._data._external_storage.huggingface import (
    HuggingfaceApi,
    _hub_path_for_repo,
    _parse_hub_path,
    _ResolvedHubPath,
)
from marimo._data._external_storage.models import (
    StorageEntry,
    StorageListResult,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._types.ids import VariableName

HAS_HF = DependencyManager.huggingface_hub.has()


class TestParseHubPath:
    def test_root(self) -> None:
        assert _parse_hub_path("") == snapshot(_ResolvedHubPath(kind="root"))
        assert _parse_hub_path("   ") == snapshot(
            _ResolvedHubPath(kind="root")
        )

    def test_dataset_repo(self) -> None:
        resolved = _parse_hub_path("datasets/scikit-learn/Fish")
        assert resolved == snapshot(
            _ResolvedHubPath(
                kind="repo",
                repo_type="dataset",
                repo_id="scikit-learn/Fish",
            )
        )

    def test_dataset_nested(self) -> None:
        resolved = _parse_hub_path("datasets/scikit-learn/Fish/data/train.csv")
        assert resolved == snapshot(
            _ResolvedHubPath(
                kind="repo",
                repo_type="dataset",
                repo_id="scikit-learn/Fish",
                path_in_repo="data/train.csv",
            )
        )

    def test_model_repo(self) -> None:
        resolved = _parse_hub_path("google/bert-base-uncased")
        assert resolved == snapshot(
            _ResolvedHubPath(
                kind="repo",
                repo_type="model",
                repo_id="google/bert-base-uncased",
            )
        )

    def test_model_nested(self) -> None:
        resolved = _parse_hub_path("google/bert-base-uncased/weights.bin")
        assert resolved == snapshot(
            _ResolvedHubPath(
                kind="repo",
                repo_type="model",
                repo_id="google/bert-base-uncased",
                path_in_repo="weights.bin",
            )
        )

    def test_bucket(self) -> None:
        # Bucket ids are namespaced like repo ids ("namespace/bucket-name").
        resolved = _parse_hub_path(
            "buckets/my-org/my-bucket/data/file.parquet"
        )
        assert resolved == snapshot(
            _ResolvedHubPath(
                kind="bucket",
                bucket_id="my-org/my-bucket",
                path_in_repo="data/file.parquet",
            )
        )

    def test_bucket_repo_root(self) -> None:
        resolved = _parse_hub_path("buckets/my-org/my-bucket")
        assert resolved == snapshot(
            _ResolvedHubPath(kind="bucket", bucket_id="my-org/my-bucket")
        )

    def test_bucket_incomplete(self) -> None:
        with pytest.raises(
            ValueError, match="Incomplete Hugging Face Hub path"
        ):
            _parse_hub_path("buckets/my-bucket")

    def test_ignores_empty_segments_from_double_slashes(self) -> None:
        # A double slash shouldn't leak an empty segment into repo_id/
        # namespaced_id, matching the frontend's `.filter(Boolean)`.
        assert _parse_hub_path("datasets//scikit-learn/Fish") == snapshot(
            _ResolvedHubPath(
                kind="repo",
                repo_type="dataset",
                repo_id="scikit-learn/Fish",
            )
        )
        assert _parse_hub_path("google//bert-base-uncased") == snapshot(
            _ResolvedHubPath(
                kind="repo",
                repo_type="model",
                repo_id="google/bert-base-uncased",
            )
        )
        assert _parse_hub_path(
            "google/bert-base-uncased//weights.bin"
        ) == snapshot(
            _ResolvedHubPath(
                kind="repo",
                repo_type="model",
                repo_id="google/bert-base-uncased",
                path_in_repo="weights.bin",
            )
        )


class TestHubPathForRepo:
    def test_paths(self) -> None:
        assert _hub_path_for_repo("dataset", "org/name") == "datasets/org/name"
        assert _hub_path_for_repo("space", "org/name") == "spaces/org/name"
        assert _hub_path_for_repo("model", "org/name") == "org/name"


@pytest.mark.skipif(not HAS_HF, reason="huggingface_hub not installed")
class TestHuggingfaceApi:
    def _make_backend(self, api: Any, name: str = "hf") -> HuggingfaceApi:
        return HuggingfaceApi(api, VariableName(name))

    def test_list_repo_entries(self) -> None:
        from huggingface_hub import RepoFile

        mock_api = MagicMock()
        mock_file = MagicMock(spec=RepoFile)
        mock_file.path = "Fish.csv"
        mock_file.size = 5862
        mock_file.last_commit = None
        mock_api.list_repo_tree.return_value = [mock_file]

        backend = self._make_backend(mock_api)
        result = backend.list_entries(prefix="datasets/scikit-learn/Fish")

        mock_api.list_repo_tree.assert_called_once_with(
            "scikit-learn/Fish",
            path_in_repo=None,
            repo_type="dataset",
            recursive=False,
        )
        assert result.entries == snapshot(
            [
                StorageEntry(
                    path="datasets/scikit-learn/Fish/Fish.csv",
                    kind="file",
                    size=5862,
                    last_modified=None,
                    metadata={},
                    mime_type="text/csv",
                )
            ]
        )

    def test_list_bucket_entries(self) -> None:
        from huggingface_hub import BucketFile

        mock_api = MagicMock()
        mock_file = MagicMock(spec=BucketFile)
        mock_file.path = "data/file.parquet"
        mock_file.size = 1024
        mock_file.uploaded_at = None
        mock_api.list_bucket_tree.return_value = [mock_file]

        backend = self._make_backend(mock_api)
        result = backend.list_entries(prefix="buckets/my-org/my-bucket")

        # Bucket ids are namespaced ("namespace/bucket-name"), not a single
        # path segment, so the full namespace must be forwarded to the API.
        mock_api.list_bucket_tree.assert_called_once_with(
            "my-org/my-bucket",
            prefix=None,
            recursive=False,
        )
        assert result.entries == snapshot(
            [
                StorageEntry(
                    path="buckets/my-org/my-bucket/data/file.parquet",
                    kind="file",
                    size=1024,
                    last_modified=None,
                    metadata={},
                    mime_type=None,
                )
            ]
        )

    def test_list_root_entries_with_author(self) -> None:
        mock_api = MagicMock()
        mock_api.whoami.return_value = {"name": "marimo-team"}
        mock_dataset = MagicMock()
        mock_dataset.id = "marimo-team/demo"
        mock_api.list_datasets.return_value = [mock_dataset]
        mock_api.list_models.return_value = []
        mock_api.list_spaces.return_value = []
        mock_api.list_buckets.return_value = []

        backend = self._make_backend(mock_api)
        result = backend.list_entries(prefix="")

        mock_api.list_datasets.assert_called_once_with(
            author="marimo-team", limit=50
        )
        assert result.entries == snapshot(
            [
                StorageEntry(
                    path="datasets/marimo-team/demo",
                    kind="directory",
                    size=0,
                    last_modified=None,
                    metadata={},
                    mime_type=None,
                )
            ]
        )

    def test_list_root_entries_tolerates_partial_failures(self) -> None:
        # A transient failure in one listing call (e.g. rate limiting)
        # shouldn't prevent the others from rendering.
        mock_api = MagicMock()
        mock_api.whoami.return_value = {"name": "marimo-team"}
        mock_api.list_datasets.side_effect = Exception("rate limited")
        mock_model = MagicMock()
        mock_model.id = "marimo-team/model"
        mock_api.list_models.return_value = [mock_model]
        mock_api.list_spaces.side_effect = Exception("rate limited")
        mock_api.list_buckets.return_value = []

        backend = self._make_backend(mock_api)
        result = backend.list_entries(prefix="")

        assert result.entries == snapshot(
            [
                StorageEntry(
                    path="marimo-team/model",
                    kind="directory",
                    size=0,
                    last_modified=None,
                    metadata={},
                    mime_type=None,
                )
            ]
        )

    def test_protocol_and_backend_type(self) -> None:
        backend = self._make_backend(MagicMock())
        assert backend.protocol == "hf"
        assert backend.backend_type == "huggingface"
        assert backend.display_name == "Hugging Face Hub"
        assert backend.root_path is None

    def test_is_compatible(self) -> None:
        from huggingface_hub import HfApi

        assert HuggingfaceApi.is_compatible(HfApi()) is True
        assert HuggingfaceApi.is_compatible("not hf") is False

    @pytest.mark.asyncio
    async def test_sign_download_url(self) -> None:
        mock_api = MagicMock()
        mock_api.endpoint = "https://huggingface.co"
        backend = self._make_backend(mock_api)
        url = await backend.sign_download_url(
            "datasets/scikit-learn/Fish/Fish.csv"
        )
        assert url is not None
        assert "huggingface.co" in url
        assert "Fish.csv" in url

    @pytest.mark.asyncio
    async def test_download_repo_file(self) -> None:
        mock_api = MagicMock()
        mock_api.token = None
        mock_api.endpoint = "https://huggingface.co"
        backend = self._make_backend(mock_api)

        with patch(
            "huggingface_hub.hf_hub_download",
            return_value="/tmp/Fish.csv",
        ) as mock_download:
            with patch(
                "pathlib.Path.read_bytes",
                return_value=b"csv-data",
            ):
                data = await backend.download(
                    "datasets/scikit-learn/Fish/Fish.csv"
                )

        mock_download.assert_called_once_with(
            repo_id="scikit-learn/Fish",
            filename="Fish.csv",
            repo_type="dataset",
            token=None,
            endpoint="https://huggingface.co",
        )
        assert data == b"csv-data"

    @pytest.mark.asyncio
    async def test_download_bucket_file(self) -> None:
        mock_api = MagicMock()
        mock_api.token = None
        backend = self._make_backend(mock_api)

        def _fake_download_bucket_files(
            _bucket_id: str, files: list[tuple[str, str]], **_kwargs: Any
        ) -> None:
            _, tmp_path = files[0]
            with open(tmp_path, "wb") as f:
                f.write(b"bucket-data")

        mock_api.download_bucket_files.side_effect = (
            _fake_download_bucket_files
        )

        data = await backend.download(
            "buckets/my-org/my-bucket/data/file.parquet"
        )

        # Bucket ids are namespaced ("namespace/bucket-name"), not a single
        # path segment, so the full namespace must be forwarded to the API.
        args, kwargs = mock_api.download_bucket_files.call_args
        assert args[0] == "my-org/my-bucket"
        assert args[1][0][0] == "data/file.parquet"
        assert kwargs["token"] is None
        assert data == b"bucket-data"

    @pytest.mark.asyncio
    async def test_sign_download_url_for_bucket(self) -> None:
        mock_api = MagicMock()
        mock_api.endpoint = "https://huggingface.co"
        backend = self._make_backend(mock_api)
        url = await backend.sign_download_url(
            "buckets/my-org/my-bucket/data/file.parquet"
        )
        assert url == (
            "https://huggingface.co/buckets/my-org/my-bucket/resolve/"
            "data/file.parquet"
        )

    @pytest.mark.asyncio
    async def test_read_range_zero_length(self) -> None:
        mock_api = MagicMock()
        mock_api.endpoint = "https://huggingface.co"
        backend = self._make_backend(mock_api)

        with patch("huggingface_hub.file_download.http_get") as mock_http_get:
            data = await backend.read_range(
                "datasets/scikit-learn/Fish/Fish.csv", offset=0, length=0
            )

        mock_http_get.assert_not_called()
        assert data == b""

    def test_list_entries_pagination(self) -> None:
        mock_api = MagicMock()
        mock_api.whoami.side_effect = Exception("no auth")
        mock_api.list_datasets.return_value = []
        mock_api.list_models.return_value = []
        mock_api.list_spaces.return_value = []
        mock_api.list_buckets.return_value = []

        entries = [
            StorageEntry(
                path=f"repo-{i}",
                kind="directory",
                size=0,
                last_modified=None,
            )
            for i in range(5)
        ]
        backend = self._make_backend(mock_api)
        with patch.object(
            backend,
            "_list_storage_entries",
            return_value=entries,
        ):
            result = backend.list_entries(prefix="", limit=2)
        assert result == snapshot(
            StorageListResult(
                entries=entries[:2],
                next_page_token="2",
            )
        )
