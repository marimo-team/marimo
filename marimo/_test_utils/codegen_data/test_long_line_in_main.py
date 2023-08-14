import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def one():
    i_am_a_very_long_name = 0
    i_am_another_very_long_name = 0
    yet_another_very_long_name = 0
    return (
        i_am_a_very_long_name,
        i_am_another_very_long_name,
        yet_another_very_long_name,
    )


@app.cell
def two(
    i_am_a_very_long_name,
    i_am_another_very_long_name,
    yet_another_very_long_name,
):
    z = i_am_a_very_long_name + i_am_another_very_long_name + yet_another_very_long_name
    return z,


if __name__ == "__main__":
    app.run()
