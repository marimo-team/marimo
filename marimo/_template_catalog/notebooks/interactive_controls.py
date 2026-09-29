# Copyright 2026 Marimo. All rights reserved.
import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    team_size = mo.ui.slider(
        start=1,
        stop=50,
        value=8,
        label="Team size",
    )
    cost_per_person = mo.ui.number(
        start=0,
        value=25,
        label="Monthly cost per person ($)",
    )
    fixed_cost = mo.ui.number(
        start=0,
        value=100,
        label="Fixed monthly cost ($)",
    )
    mo.vstack([team_size, cost_per_person, fixed_cost])
    return cost_per_person, fixed_cost, team_size


@app.cell
def _(cost_per_person, fixed_cost, mo, team_size):
    monthly_total = fixed_cost.value + team_size.value * cost_per_person.value
    mo.md(f"""
    # Monthly budget calculator

    **Estimated monthly cost: ${monthly_total:,.0f}**

    {team_size.value} people × ${cost_per_person.value:,.0f}, plus
    ${fixed_cost.value:,.0f} in fixed costs.
    """)
    return


if __name__ == "__main__":
    app.run()
