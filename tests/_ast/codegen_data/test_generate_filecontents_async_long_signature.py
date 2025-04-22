import marimo

__generated_with = "0.4.0"
app = marimo.App()


@app.cell
def one():
    (
        client,
        get_calculation_trigger,
        get_components_configuration,
        get_conditions_state,
    ) = (1, 1, 1, 1)
    return (
        client,
        get_calculation_trigger,
        get_components_configuration,
        get_conditions_state,
    )


@app.cell
async def two(
    client,
    get_calculation_trigger,
    get_components_configuration,
    get_conditions_state,
):
    _conditions = [c for c in get_conditions_state().values()]
    _configuration = get_components_configuration()

    _configuration_conditions_list = {
        "configuration": _configuration,
        "condition": _conditions,
    }

    _trigger = get_calculation_trigger()

    async for data_point in client("test", "ws://localhost:8000"):
        print(data_point)
    data_point
    return


if __name__ == "__main__":
    app.run()
