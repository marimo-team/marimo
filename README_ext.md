# Marimo LLM Agent Extension

This fork is a modified version of Marimo with support for executing LLM agents from cells. Some features may interfere with Marimo's original functionality, so use with caution.

## Feature overview

### Agent Registry

The agent registry is a new feature that allows users to register LLM agents (e.g. LangChain, LangGraph) with the Marimo UI. The cell input can be set as a plain-text input to the agent, with the cell output representing the agent's response.

Usage:


### Background Datasource Variable Registration

> [!CAUTION]
> This function may cause unintended bugs in Marimo's reactivity, since
> defined variables cannot be statically analyzed. Also, this can be
> confusing for users if used inappropriately to flood the global scope.
> Please be mindful of this function.

This feature allows LLM agents designed to work with this version of Marimo
to emit variables to the global scope. This is useful for agents that 
make tool calls and want to implicitly assign intermediate fetched data to
variables.
