# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Final,
    Literal,
    Optional,
    TypedDict,
    Union,
)

from marimo import _loggers
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.validators import validate_one_of
from marimo._runtime.functions import Function
from marimo._utils.files import natural_sort

LOGGER = _loggers.marimo_logger()


@dataclass
class ListDirectoryArgs:
    path: str


@dataclass
class FileBrowserFileInfo:
    id: str
    path: Path
    name: str
    is_directory: bool


class TypedFileBrowserFileInfo(TypedDict):
    id: str
    path: str
    name: str
    is_directory: bool


@dataclass
class ListDirectoryResponse:
    files: list[TypedFileBrowserFileInfo]


@mddoc
class file_browser(
    UIElement[list[TypedFileBrowserFileInfo], Sequence[FileBrowserFileInfo]]
):
    """File browser for browsing and selecting server-side files.
    This element supports local files, S3, GCS, and Azure.

    Examples:
        Selecting multiple files:
        ```python
        file_browser = mo.ui.file_browser(
            initial_path=Path("path/to/dir"), multiple=True
        )

        # Access the selected file path(s):
        file_browser.path(index=0)  # returns a Path object

        # Get name of selected file(s)
        file_browser.name(index=0)
        ```

        Connecting to an S3 (or GCS, Azure) bucket:
        ```python
        from cloudpathlib import S3Path

        file_browser = mo.ui.file_browser(
            initial_path=S3Path("s3://my-bucket/folder/")
        )

        # Access the selected file path(s):
        file_browser.path(index=0)  # returns a S3Path object

        # Read the contents of the selected file(s):
        file_browser.path(index=0).read_text()
        ```

        Using with client credentials:
        ```python
        from cloudpathlib import GSClient, GSPath

        # Create a client with credentials
        gs_client = GSClient("storage_credentials.json", project="my-project")

        # Create a path with the client
        cloudpath = GSPath("gs://my-bucket/folder", client=gs_client)

        # Use the path with file_browser
        file_browser = mo.ui.file_browser(initial_path=cloudpath)
        ```

    Attributes:
        value (Sequence[FileInfo]): A sequence of file paths representing selected
            files.

    Args:
        initial_path (Union[str, Path, AnyPath], optional): Starting directory. Defaults to current
            working directory.
            If a string, it will be interpreted as a local path.
            If a Path, it will be interpreted as a local path.
            If a CloudPath (from cloudpathlib), such as S3Path, GCSPath, or AzurePath,
            files will be loaded from the respective cloud storage bucket.
            If a CloudPath with a client is provided, that client will be used for all operations.
        filetypes (Sequence[str], optional): The file types to display in each
            directory; for example, filetypes=[".txt", ".csv"]. If None, all
            files are displayed. Defaults to None.
        selection_mode (Literal["file", "directory"], optional): Either "file" or "directory". Defaults to
            "file".
        multiple (bool, optional): If True, allow the user to select multiple
            files. Defaults to True.
        restrict_navigation (bool, optional): If True, prevent the user from
            navigating any level above the given path. Defaults to False.
        limit (int, optional): Maximum number of files to display. Defaults to 50.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Callable[[Sequence[FileInfo]], None], optional): Optional
            callback to run when this element's value changes. Defaults to None.
    """

    _name: Final[str] = "marimo-file-browser"

    def __init__(
        self,
        initial_path: Union[str, Path] = "",
        filetypes: Optional[Sequence[str]] = None,
        selection_mode: Literal["file", "directory"] = "file",
        multiple: bool = True,
        restrict_navigation: bool = False,
        *,
        limit: int = 50,
        label: str = "",
        on_change: Optional[
            Callable[[Sequence[FileBrowserFileInfo]], None]
        ] = None,
    ) -> None:
        validate_one_of(selection_mode, ["file", "directory"])

        if not initial_path:
            initial_path = Path.cwd()
        elif isinstance(initial_path, str):
            initial_path = Path(initial_path)

        # frontend plugin can't handle relative paths
        initial_path = initial_path.resolve()
        # initial path must be a directory
        if not initial_path.is_dir():
            raise ValueError(
                f"Initial path {initial_path} is not a directory."
            )

        self._selection_mode = selection_mode
        self._filetypes: set[str] = set(filetypes) if filetypes else set()
        self._restrict_navigation = restrict_navigation
        self._initial_path: Path = initial_path
        self._limit = limit

        self._path_cls: type[Path]
        if isinstance(initial_path, str):
            self._path_cls = Path
        else:
            self._path_cls = initial_path.__class__

        super().__init__(
            component_name=file_browser._name,
            initial_value=[],
            label=label,
            args={
                "initial-path": str(initial_path),
                "selection-mode": selection_mode,
                "filetypes": filetypes if filetypes is not None else [],
                "multiple": multiple,
                "restrict-navigation": restrict_navigation,
            },
            functions=(
                Function(
                    name="list_directory",
                    arg_cls=ListDirectoryArgs,
                    function=self._list_directory,
                ),
            ),
            on_change=on_change,
        )

    def _create_path(self, path_str: str) -> Path:
        """Create a path object with the same class and client as the initial path."""
        kwargs: dict[str, Any] = {}

        # If we have a client on the initial path, pass it to the path constructor
        # This covers the case when the initial path is a CloudPath with a client
        if hasattr(self._initial_path, "client"):
            kwargs["client"] = self._initial_path.client  # type: ignore

        path = self._path_cls(path_str, **kwargs)
        return path

    def _list_directory(
        self, args: ListDirectoryArgs
    ) -> ListDirectoryResponse:
        # When navigation is restricted, the navigated-to path cannot be
        # be a parent of the initial path

        # Convert to original class of initial_path
        # so that it works with anything that extended Path
        # such as CloudPath
        path = self._create_path(args.path)

        if self._restrict_navigation and path in self._initial_path.parents:
            raise RuntimeError(
                "Navigation is restricted; navigating to a "
                "parent of initial path is not allowed."
            )
        folders: list[TypedFileBrowserFileInfo] = []
        files: list[TypedFileBrowserFileInfo] = []

        for file in path.iterdir():
            extension = file.suffix
            is_directory = file.is_dir()

            # Skip non-directories if selection mode is directory
            if self._selection_mode == "directory" and not is_directory:
                continue

            # Skip non-matching file types
            if self._filetypes and not is_directory:
                if extension not in self._filetypes:
                    continue

            file_info = TypedFileBrowserFileInfo(
                id=str(file),
                path=str(file),
                name=file.name,
                is_directory=is_directory,
            )

            if is_directory:
                folders.append(file_info)
            else:
                files.append(file_info)

            if len(folders) + len(files) >= self._limit:
                break

        def natural_sort_info(
            info: TypedFileBrowserFileInfo,
        ) -> list[Union[int, str]]:
            return natural_sort(info["name"])

        # Sort folders then files, based on natural sort (alpha, then num)
        all_files = sorted(folders, key=natural_sort_info) + sorted(
            files, key=natural_sort_info
        )
        return ListDirectoryResponse(all_files)

    def _convert_value(
        self, value: list[TypedFileBrowserFileInfo]
    ) -> Sequence[FileBrowserFileInfo]:
        return tuple(
            FileBrowserFileInfo(
                id=file["id"],
                name=file["name"],
                path=self._create_path(file["path"]),
                is_directory=file["is_directory"],
            )
            for file in value
        )

    def name(self, index: int = 0) -> Optional[str]:
        """Get file name at index.

        Args:
            index (int, optional): Index of the file to get the name from.
                Defaults to 0.

        Returns:
            Optional[str]: The name of the file at the specified index,
                or None if index is out of range.
        """
        if not self.value or index >= len(self.value):
            return None
        else:
            return self.value[index].name

    def path(self, index: int = 0) -> Optional[Path]:
        """Get file path at index.

        Args:
            index (int, optional): Index of the file to get the path from.
                Defaults to 0.

        Returns:
            Optional[str]: The path of the file at the specified index,
                or None if index is out of range.
        """
        if not self.value or index >= len(self.value):
            return None
        else:
            return self.value[index].path
