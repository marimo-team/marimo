#!/usr/bin/env python3
"""Script to convert Sphinx directives to MkDocs Material format."""

import os
import re
from pathlib import Path

def convert_admonition(content):
    """Convert Sphinx admonition to MkDocs Material format."""
    # Convert ```{admonition} Title to !!! type "Title"
    content = re.sub(
        r'```\{admonition\}\s*(.*?)\n:class:\s*(.*?)\n',
        r'!!! \2 "\1"\n',
        content,
        flags=re.MULTILINE,
    )

    # Convert :::{admonition} Title to !!! type "Title"
    content = re.sub(
        r':::\{admonition\}\s*(.*?)\n:class:\s*(.*?)\n',
        r'!!! \2 "\1"\n',
        content,
        flags=re.MULTILINE,
    )

    # Remove closing ``` or ::: for admonitions
    content = re.sub(r'```\n(?=\s*$)', '', content, flags=re.MULTILINE)
    content = re.sub(r':::\n(?=\s*$)', '', content, flags=re.MULTILINE)

    return content

def convert_internal_references(content):
    """Convert internal module references to public API paths."""
    # Convert marimo._plugins references to public API paths
    replacements = [
        (r'marimo\._plugins\.stateless\.mermaid\.mermaid', r'marimo.mermaid'),
        (r'marimo\._plugins\.stateless\.(\w+)\.(\w+)', r'marimo.\1'),
        (r'marimo\._plugins\.ui\._impl\.(\w+)\.(\w+)', r'marimo.\1'),
        (r'marimo\._runtime\.(\w+)', r'marimo.\1'),
        # Handle direct references in autofunction/autoclasstoc
        (r'\.\. autofunction:: marimo\._plugins\.stateless\.(\w+)\.(\w+)', r'.. autofunction:: marimo.\1'),
        (r'\.\. autoclasstoc:: marimo\._plugins\.stateless\.(\w+)\.(\w+)', r'.. autoclasstoc:: marimo.\1'),
        (r'\.\. autofunction:: marimo\._plugins\.ui\._impl\.(\w+)\.(\w+)', r'.. autofunction:: marimo.\1'),
        (r'\.\. autoclasstoc:: marimo\._plugins\.ui\._impl\.(\w+)\.(\w+)', r'.. autoclasstoc:: marimo.\1'),
        # Handle mkdocstrings format
        (r'::: marimo\._plugins\.stateless\.(\w+)\.(\w+)', r'::: marimo.\1'),
        (r'::: marimo\._plugins\.ui\._impl\.(\w+)\.(\w+)', r'::: marimo.\1'),
    ]

    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)

    return content

def convert_eval_rst(content):
    """Convert eval-rst blocks to mkdocstrings format."""
    # Convert ```{eval-rst} blocks to ::: mkdocstrings
    content = re.sub(
        r'```\{eval-rst\}\n(.*?)```',
        lambda m: convert_rst_block(m.group(1)),
        content,
        flags=re.DOTALL,
    )
    # Convert {eval-rst} blocks without backticks
    content = re.sub(
        r'\{eval-rst\}\n(.*?)\n\s*(?=\n|$)',
        lambda m: convert_rst_block(m.group(1)),
        content,
        flags=re.DOTALL,
    )
    return content

def convert_rst_block(content):
    """Convert various RST directives to mkdocstrings format."""
    # Convert autofunction directives
    content = re.sub(
        r'\.\.\s*autofunction::\s*([\w\.]+)',
        r'::: \1\n    options:\n      show_root_heading: true\n      show_source: true',
        content
    )

    # Convert autoclasstoc directives
    content = re.sub(
        r'\.\.\s*autoclasstoc::\s*([\w\.]+)',
        r'::: \1\n    options:\n      show_root_heading: true\n      show_source: true\n      members: true',
        content
    )

    # Convert internal references to public API paths
    content = convert_internal_references(content)

    return content

def convert_file(file_path):
    """Convert a single file from Sphinx to MkDocs format."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Convert various Sphinx directives to MkDocs Material format
    content = convert_admonition(content)
    content = convert_eval_rst(content)
    content = convert_internal_references(content)

    # Fix relative links
    content = re.sub(r'\[([^\]]+)\]\(/([^\)]+)\)', r'[\1](../\2)', content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    """Convert all documentation files in the docs directory."""
    docs_dir = Path('/home/ubuntu/repos/marimo/docs')
    for file_path in docs_dir.rglob('*.md'):
        if file_path.is_file():
            print(f'Converting {file_path}...')
            convert_file(file_path)

if __name__ == '__main__':
    main()
