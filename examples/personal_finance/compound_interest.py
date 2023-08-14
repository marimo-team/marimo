import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Compound Interest")
    return


@app.cell
def __(mo):
    mo.md(
        """
        This notebook illustrates exponential growth, using compound interest
        as an example.
        """
    ).callout()
    return


@app.cell
def __(mo):
    initial_investment = mo.ui.slider(0, 1000000, step=1e4, value=10000)
    monthly_investment = mo.ui.slider(0, 50000, value=1000, step=1e3)
    annual_return = mo.ui.slider(0, 0.15, value=0.07, step=0.01)
    years = mo.ui.slider(1, 60, value=30)
    capital_gains_tax_rate = mo.ui.slider(0.0, 1.0, value=0.32, step=0.01)

    table = mo.ui.table(
        [
            {
                "parameter": "initial investment",
                "control": initial_investment,
            },
            {
                "parameter": "monthly investment",
                "control": monthly_investment,
            },
            {
                "parameter": "annual return",
                "control": annual_return,
            },
            {
                "parameter": "years",
                "control": years,
            },
            {
                "parameter": "capital gains tax rate",
                "control": capital_gains_tax_rate,
            },
        ],
        selection=None,
    )

    mo.md(
        f"""## Investment Parameters
        
        {table}
        """)
    return (
        annual_return,
        capital_gains_tax_rate,
        initial_investment,
        monthly_investment,
        table,
        years,
    )


@app.cell
def simulate(
    annual_return,
    capital_gains_tax_rate,
    initial_investment,
    mo,
    monthly_investment,
    plt,
    years,
):
    class Portfolio:
        def __init__(self, value, annual_return):
            self.value = value
            self.annual_return = annual_return
            self.monthly_return = (1 + self.annual_return) ** (1.0 / 12) - 1

        def simulate_month(self, additional_investment):
            self.value += additional_investment
            self.value *= 1 + self.monthly_return
            return self.value

        def total_return(self, months):
            return (1 + self.monthly_return) ** months


    portfolio = Portfolio(initial_investment.value, annual_return.value)
    values = [portfolio.value]
    investment_principals = [portfolio.value]
    values_less_taxes = [portfolio.value]

    _months = years.value * 12
    for _ in range(_months):
        values.append(portfolio.simulate_month(monthly_investment.value))
        investment_principals.append(
            investment_principals[-1] + monthly_investment.value
        )
        values_less_taxes.append(
            investment_principals[-1]
            + (1 - capital_gains_tax_rate.value)
            * (values[-1] - investment_principals[-1])
        )

    plt.plot(values, label="Portfolio Value")
    plt.plot(values_less_taxes, label="Value, Less Capital Gains Taxes")
    plt.plot(investment_principals, label="Contributed")
    plt.legend()
    plt.xlabel("Month")
    plt.title("Net Wealth")

    _prose = f"""
    ## Net Worth

    With an initial investment of **\${initial_investment.value :,.02f}**, an annual
    return of **{annual_return.value * 100:.02f}%** with
    **\${monthly_investment.value:,.02f}** invested monthly, in {years.value} years
    you will have approximately **\${values[-1]:,.02f}** accumulated in
    equities. Assuming a long-term capitals gain tax of
    **{capital_gains_tax_rate.value*100:.02f}%**, the net portfolio value is
    **\${values_less_taxes[-1]:,.02f}**. Compare that to the
    **\${investment_principals[-1]:,.02f}** that you contributed in total.
    """

    ax = plt.gca()
    mo.md(_prose)
    return (
        Portfolio,
        ax,
        investment_principals,
        portfolio,
        values,
        values_less_taxes,
    )


@app.cell
def __(ax):
    ax
    return


@app.cell
def __():
    import marimo as mo
    import matplotlib.pyplot as plt
    return mo, plt


if __name__ == "__main__":
    app.run()
