"""Update mkdocs.yml configuration for handling private modules."""
import yaml
from pathlib import Path

def update_mkdocs_config():
    """Update mkdocs.yml configuration."""
    config_path = Path('../mkdocs.yml')
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Find mkdocstrings plugin in the list
    for plugin in config['plugins']:
        if isinstance(plugin, dict) and 'mkdocstrings' in plugin:
            plugin['mkdocstrings']['handlers']['python']['selection'] = {
                'filters': {
                    'value': ['!^_[^_]', '!^__[^_]']  # Allow _plugins but not other single/double underscore
                }
            }
            break

    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

if __name__ == '__main__':
    update_mkdocs_config()
