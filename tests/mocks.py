from __future__ import annotations

import os
from typing import Callable


def snapshotter(current_file: str) -> Callable[[str, str], None]:
    def snapshot(filename: str, result: str) -> None:
        filepath = os.path.join(os.path.dirname(current_file), "snapshots", filename)

        # If snapshot directory doesn't exist, create it
        if not os.path.exists(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath))

        # If doesn't exist, create snapshot
        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                f.write(result)
            print("Snapshot updated")

        # Read snapshot
        with open(filepath, "r") as f:
            expected = f.read()

        with open(filepath, "w") as f:
            f.write(result)
        assert result == expected

    return snapshot
