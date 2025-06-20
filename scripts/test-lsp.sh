#!/usr/bin/env bash
list_directories() {
    # List out contents of the directories
    tree marimo/_lsp
    tree lsp/dist
}


list_directories

if [ -d "marimo/_lsp/copilot/dist" ]; then
    echo "Error: marimo/_lsp/copilot should not have a dist/ directory"
    list_directories
    exit 1
fi
echo "Copilot directory structure looks correct."


node marimo/_lsp/index.cjs --help > /dev/null
if [ $? -ne 0 ]; then
    echo "LSP binary failed to start"
    list_directories
    exit 1
fi
echo "LSP binary started successfully"
