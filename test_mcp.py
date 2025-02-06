import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    # Create a server
    server = mo.mcp.Server(name="my-server")

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
def _():
    from marimo._mcp import registry

    return (registry,)


@app.cell
def _(registry, server):
    registry.register_server(server)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
