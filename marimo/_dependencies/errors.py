from __future__ import annotations


class ManyModulesNotFoundError(ModuleNotFoundError):
    """
    Raised when multiple modules are not found.
    """

    package_names: list[str]

    def __init__(self, package_names: list[str], msg: str) -> None:
        self.package_names = package_names
        super().__init__(msg)
