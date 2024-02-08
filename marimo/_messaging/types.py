# Copyright 2024 Marimo. All rights reserved.
from typing import Any, Tuple

# The message from the kernel is a tuple of message type
# and a json representation of the message
KernelMessage = Tuple[str, Any]
