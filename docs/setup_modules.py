"""Set up Python modules for documentation."""
import os
from pathlib import Path

def create_init_files():
    """Create __init__.py files in necessary directories."""
    marimo_dir = Path('../marimo')

    # Directories that need __init__.py files
    dirs_needing_init = [
        '_plugins',
        '_plugins/stateless',
        '_plugins/stateless/status',
        '_plugins/stateless/mpl',
        '_plugins/ui',
        '_plugins/ui/_core',
        '_plugins/ui/_impl',
        '_plugins/ui/_impl/chat',
        '_plugins/ui/_impl/anywidget',
        '_plugins/ui/_impl/tables',
        '_plugins/ui/_impl/utils',
        '_plugins/ui/_impl/charts',
        '_plugins/ui/_impl/dataframes',
        '_plugins/ui/_impl/dataframes/transforms'
    ]

    # Create __init__.py files
    for dir_path in dirs_needing_init:
        init_file = marimo_dir / dir_path / '__init__.py'
        if not init_file.exists():
            init_file.parent.mkdir(parents=True, exist_ok=True)
            init_file.touch()
            print(f'Created {init_file}')

if __name__ == '__main__':
    create_init_files()
