# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Callable,
    Final,
    Optional,
    TypedDict,
    Union,
)

from marimo import _loggers
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.functions import Function

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
        file_browser.path(index)  # returns a Path object

        # Get name of selected file(s)
        file_browser.name(index)
        ```

        Connecting to an S3 (or GCS, Azure) bucket:
        ```python
        from cloudpathlib import S3Path

        file_browser = mo.ui.file_browser(
            initial_path=S3Path("s3://mybucket/mydir")
        )

        # Access the selected file path(s):
        file_browser.path(index)  # returns a S3Path object

        # Read the contents of the selected file(s):
        file_browser.path(index).read_text()
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
        filetypes (Sequence[str], optional): The file types to display in each
            directory; for example, filetypes=[".txt", ".csv"]. If None, all
            files are displayed. Defaults to None.
        selection_mode (str, optional): Either "file" or "directory". Defaults to
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
        selection_mode: str = "file",
        multiple: bool = True,
        restrict_navigation: bool = False,
        *,
        limit: int = 50,
        label: str = "",
        on_change: Optional[
            Callable[[Sequence[FileBrowserFileInfo]], None]
        ] = None,
    ) -> None:
        if (
            selection_mode != "file"
            and selection_mode != "directory"
            and selection_mode != "all"
        ):
            raise ValueError(
                "Invalid argument for selection_mode. "
                + "Must be either 'file' or 'directory'."
            )
        else:
            self.selection_mode = selection_mode

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

        self.filetypes: set[str] = set(filetypes) if filetypes else set()
        self.restrict_navigation = restrict_navigation
        self.initial_path: Path = initial_path
        self.limit = limit

        self.path_cls: type[Path]
        if isinstance(initial_path, str):
            self.path_cls = Path
        else:
            self.path_cls = initial_path.__class__

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

    def _list_directory(
        self, args: ListDirectoryArgs
    ) -> ListDirectoryResponse:
        # When navigation is restricted, the navigated-to path cannot be
        # be a parent of the initial path

        # Convert to original class of initial_path
        # so that it works with anything that extended Path
        # such as CloudPath
        path = self.path_cls(args.path)

        if self.restrict_navigation and path in self.initial_path.parents:
            raise RuntimeError(
                "Navigation is restricted; navigating to a "
                "parent of initial path is not allowed."
            )

        files: list[TypedFileBrowserFileInfo] = []
        for file in path.iterdir():
            _, extension = os.path.splitext(file.name)

            # Skip non-directories if selection mode is directory
            if self.selection_mode == "directory" and not file.is_dir():
                continue

            # Skip non-matching file types
            if self.filetypes and not file.is_dir():
                if extension not in self.filetypes:
                    continue

            files.append(
                TypedFileBrowserFileInfo(
                    id=str(file),
                    path=str(file),
                    name=file.name,
                    is_directory=file.is_dir(),
                )
            )

            if len(files) >= self.limit:
                break

        return ListDirectoryResponse(files)

    def _convert_value(
        self, value: list[TypedFileBrowserFileInfo]
    ) -> Sequence[FileBrowserFileInfo]:
        return tuple(
            FileBrowserFileInfo(
                id=file["id"],
                name=file["name"],
                path=self.path_cls(file["path"]),
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
