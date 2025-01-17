import re
from pathlib import Path
from typing import Any


def on_page_markdown(markdown: str, **kwargs: Any) -> str:
    del kwargs
    static_dir = Path("docs/")
    if not static_dir.exists():
        return markdown

    # Find all src="/" patterns
    pattern = r'src="(/[^"]+)"'
    matches = re.finditer(pattern, markdown)

    for match in matches:
        src_path = match.group(1)
        # Remove leading slash and check if file exists in _static
        relative_path = src_path.lstrip("/")
        full_path = static_dir / relative_path

        if not full_path.exists():
            print(f"⚠️  Warning: Static asset not found: {src_path}")
            print(f"   Expected at: {full_path}")

    return markdown
