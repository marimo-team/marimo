import marimo

__generated_with = "0.10.12"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    # Create a server
    server = mo.mcp.MCPServer(name="my-server")


    # Add tools, resources, and prompts
    @server.tool
    def calculate_sum(a: int, b: int) -> int:
        """Calculate the sum of two numbers."""
        return a + b


    @server.resource
    def get_data():
        """Get some data."""
        return {"data": [1, 2, 3]}


    @server.prompt
    def python_help():
        """Get help writing Python code."""
        return "I can help you write Python code."
    return calculate_sum, get_data, python_help, server


@app.cell
def _(mo):
    # Create a server
    another_server = mo.mcp.MCPServer(name="another-server")
    return (another_server,)


@app.cell
def _():
    # # Start the server
    # server.start()

    # # Register with the global registry
    # from marimo._mcp.registry import registry

    # registry.register(server)
    return


if __name__ == "__main__":
    app.run()
