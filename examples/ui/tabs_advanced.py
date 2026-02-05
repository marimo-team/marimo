# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Tabs
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Use `mo.ui.tabs` to organize outputs.
    """)
    return


@app.cell
def _(mo):
    settings = mo.vstack(
        [
            mo.md("Edit User"),
            first := mo.ui.text(label="First Name"),
            last := mo.ui.text(label="Last Name"),
        ]
    )

    organization = mo.vstack(
        [
            mo.md("Edit Organization"),
            org := mo.ui.text(label="Organization Name", value="..."),
            employees := mo.ui.number(
                label="Number of Employees", start=0, stop=1000
            ),
        ]
    )

    mo.ui.tabs(
        {
            "🧙‍♀ User": settings,
            "🏢 Organization": organization,
        }
    )
    return employees, first, last, org


@app.cell
def _(employees, first, last, mo, org):
    mo.md(
        f"""
        Welcome **{first.value} {last.value}** to **{org.value}**! You are 
        employee no. **{employees.value + 1}**.

        #{"🎉" * (min(employees.value + 1, 1000))} 
        """
    ) if all([first.value, last.value, org.value]) else mo.md(
        "Type a first and last name!"
    )
    return


if __name__ == "__main__":
    app.run()
