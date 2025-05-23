#!/usr/bin/env bash
node marimo/_lsp/index.cjs --help > /dev/null
if [ $? -ne 0 ]; then
    echo "LSP binary failed to start"
    exit 1
fi
echo "LSP binary started successfully"
