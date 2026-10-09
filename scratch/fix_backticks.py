import os
import re

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Match exactly two backticks, followed by 1 or more characters that aren't backticks, 
    # followed by exactly two backticks.
    # We use negative lookbehind and lookahead to ensure there are no adjacent backticks.
    new_content = re.sub(r'(?<!`)``([^`]+)``(?!`)', r'`\1`', content)

    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk('marimo'):
    # skip _static and _lsp
    if '_static' in dirs:
        dirs.remove('_static')
    if '_lsp' in dirs:
        dirs.remove('_lsp')
        
    for file in files:
        if file.endswith('.py'):
            process_file(os.path.join(root, file))
