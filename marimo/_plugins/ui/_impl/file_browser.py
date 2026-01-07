# Copyright 2026 Marimo. All rights reserved.
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
from marimo._utils.paths import normalize_path

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
    total_count: int
    is_truncated: bool = False  # Whether results were truncated due to limit


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
        ignore_empty_dirs (bool, optional): If True, hide directories that contain
            no files (recursively). Directories are scanned up to 100 levels deep
            to prevent stack overflow from deeply nested structures. Directory
            symlinks are skipped during traversal to prevent infinite loops.
            Filetype filtering is applied recursively and is case-insensitive.
            This may impact performance for large directory trees. Defaults to False.
        limit (int, optional): Maximum number of files to display.
            If None (default), automatically chooses 50 for cloud storage (S3, GCS, Azure)
            or 10000 for local filesystems. Set explicitly to override defaults.
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
        limit: Optional[int] = None,
        label: str = "",
        on_change: Optional[
            Callable[[Sequence[FileBrowserFileInfo]], None]
        ] = None,
        ignore_empty_dirs: bool = False,
    ) -> None:
        validate_one_of(selection_mode, ["file", "directory"])

        # Save the Path class of the initial path
        self._path_cls: type[Path]
        if isinstance(initial_path, str):
            self._path_cls = Path
        else:
            self._path_cls = initial_path.__class__

        # Make a Path object
        if not initial_path:
            initial_path = Path.cwd()
        elif isinstance(initial_path, str):
            initial_path = Path(initial_path)
        self._initial_path = initial_path

        # Frontend can't handle relative paths, so normalize it and make it absolute
        # Use normalize_path to avoid symlink resolution
        self._initial_path = self._create_path(normalize_path(initial_path))

        # initial path must be a directory
        if not initial_path.is_dir():
            raise ValueError(
                f"Initial path {initial_path} is not a directory."
            )

        self._selection_mode = selection_mode
        # Normalize filetypes: ensure lowercase and dot prefix for case-insensitive matching
        if filetypes:
            normalized_filetypes = set()
            for ft in filetypes:
                ft_lower = ft.lower()
                # Ensure dot prefix
                if not ft_lower.startswith("."):
                    ft_lower = f".{ft_lower}"
                normalized_filetypes.add(ft_lower)
            self._filetypes = normalized_filetypes
        else:
            self._filetypes = set()
        self._restrict_navigation = restrict_navigation
        self._ignore_empty_dirs = ignore_empty_dirs

        # Smart default limit based on path type
        if limit is None:
            # Check if it's a cloud path
            if self._path_cls.__module__.startswith("cloudpathlib"):
                limit = 50  # Conservative for cloud storage
            else:
                limit = 10000  # High limit for local filesystems

        self._limit = limit

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

    def _create_path(self, path_str: str | Path) -> Path:
        """Create a path object with the same class and client as the initial path."""
        kwargs: dict[str, Any] = {}

        # If we have a client on the initial path, pass it to the path constructor
        # This covers the case when the initial path is a CloudPath with a client
        if hasattr(self._initial_path, "client"):
            kwargs["client"] = self._initial_path.client  # type: ignore

        path = self._path_cls(path_str, **kwargs)
        return path

    def _has_files_recursive(
        self, directory: Path, max_depth: int = 100
    ) -> bool:
        """Check if directory contains any files (recursively).

        Returns True if the directory contains at least one file (not directory),
        either directly or in any subdirectory. Returns False if the directory
        contains only empty subdirectories or is empty.

        Safety features:
        - Directory symlinks are skipped to prevent infinite loops
        - Recursion is limited to max_depth to prevent stack overflow
        - Permission errors are handled gracefully (assumes directory has files)
        - Filetype filtering is applied case-insensitively if configured

        Args:
            directory: The directory path to check
            max_depth: Maximum recursion depth to prevent stack overflow from deeply
                      nested directories. When limit is reached, assumes directory has files for safety.

        Returns:
            bool: True if directory has files, False if empty or contains only empty dirs
        """
        if max_depth <= 0:
            # Reached maximum depth, assume directory might have files to be safe
            return True

        try:
            for item in directory.iterdir():
                if item.is_file():
                    # Apply filetype filter if specified (case-insensitive)
                    if (
                        self._filetypes
                        and item.suffix.lower() not in self._filetypes
                    ):
                        continue
                    return True
                elif item.is_dir() and not item.is_symlink():
                    # Skip directory symlinks to avoid infinite loops
                    # Recursively check subdirectories with decremented depth
                    if self._has_files_recursive(item, max_depth - 1):
                        return True
            return False
        except (PermissionError, OSError):
            # If we can't access the directory, assume it's not empty
            # to avoid hiding potentially accessible subdirectories
            return True

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

        # Sort based on natural sort (alpha, then num)
        all_file_paths = sorted(
            list(path.iterdir()), key=lambda f: natural_sort(f.name)
        )
        is_truncated = False

        for files_examined, file in enumerate(all_file_paths, 1):
            extension = file.suffix
            is_directory = file.is_dir()  # Expensive call for cloud paths

            # Skip non-directories if selection mode is directory
            if self._selection_mode == "directory" and not is_directory:
                continue

            # Skip non-matching file types (case-insensitive)
            if self._filetypes and not is_directory:
                if extension.lower() not in self._filetypes:
                    continue

            # Skip empty directories if ignore_empty_dirs is enabled
            if self._ignore_empty_dirs and is_directory:
                if not self._has_files_recursive(file):
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
                # handles the case where limit equals exactly the number of items
                is_truncated = files_examined < len(all_file_paths)
                break

        # Display folders first, then files
        all_files = folders + files

        return ListDirectoryResponse(
            files=all_files,
            total_count=len(all_file_paths),
            is_truncated=is_truncated,
        )

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
