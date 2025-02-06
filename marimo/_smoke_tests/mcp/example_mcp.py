import marimo

__generated_with = "0.11.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import random
    return mo, random


@app.cell
def _(mo, random):
    server = mo.mcp.Server("local")


    @server.tool()
    def random_number():
        return random.randint(1, 100)


    @server.prompt()
    def what_are_my_tools():
        return "List the tools i have"


    mo.mcp.registry.register_server(server)
    return random_number, server, what_are_my_tools


@app.cell
async def _(server):
    from marimo._runtime.requests import MCPEvaluationRequest

    await server.evaluate_request(
        MCPEvaluationRequest(
            mcp_evaluation_id="1",
            server_name="local",
            request_type="tool",
            name="random_number",
            args={},
        )
    )
    return (MCPEvaluationRequest,)


if __name__ == "__main__":
    app.run()
