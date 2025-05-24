#!/usr/bin/env bash
node marimo/_lsp/index.cjs --help > /dev/null
if [ $? -ne 0 ]; then
    echo "LSP binary failed to start"
    # List out contents of the directory
    tree marimo/_lsp
    tree lsp/dist
    exit 1
fi
echo "LSP binary started successfully"
