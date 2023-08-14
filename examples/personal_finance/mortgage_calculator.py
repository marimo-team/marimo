import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Mortgage Calculator")
    return


@app.cell
def __(mo):
    mo.md("## Income")
    return


@app.cell
def __(mo):
    income = mo.ui.number(1, 1e8, step=50, value=100, label="income (thousands)")
    retirement_contribution = mo.ui.number(10, 40, step=10, value=19.5)

    mo.md(
        f"""
        How much do you expect to make this year, **after taxes**?
        
        {income.center()}
        """
    )
    return income, retirement_contribution


@app.cell
def __(mo):
    mo.callout(
        mo.md(
            """
            **Heads-up!**
            
            This calculator does not take taxes into account. Please make sure
            that you provide **after-tax** income. Also exclude 401k contributions.
            
            You can estimate your federal and state taxes using an online 
            calculator, such as the one
            [linked here](https://smartasset.com/taxes/income-taxes).
            """
        ),
        kind="warn",
    )
    return


@app.cell
def __(income, mo, np, retirement_contribution):
    standard_deduction = 25100
    taxable_income = (
        income.value * 1000
        - standard_deduction
        - retirement_contribution.value * 1000
    )


    def calculate_federal_tax(income):
        brackets = [
            (0.10, 0, 20550),
            (0.12, 20551, 83550),
            (0.22, 83551, 178150),
            (0.24, 178151, 340100),
            (0.32, 340101, 431900),
            (0.35, 431901, 647850),
            (0.37, 647850, np.inf),
        ]

        tax = 0
        for rate, low, high in brackets:
            tax += rate * (min(income, high) - low)
            if income <= high:
                break
        return tax


    fed_tax = calculate_federal_tax(taxable_income)
    ca_tax = 5390.38 + 0.093 * (taxable_income - 122428)

    net_cash = income.value * 1000
    net_cash_per_month = net_cash / 12

    mo.md(
        f"""
        With an after-tax income of **\${income.value*1000:,}**, you'll take home 
        **\${net_cash_per_month:,.02f}** every month.
        """
    )
    return (
        ca_tax,
        calculate_federal_tax,
        fed_tax,
        net_cash,
        net_cash_per_month,
        standard_deduction,
        taxable_income,
    )


@app.cell
def __(mo):
    home_price = mo.ui.number(
        100, 5000, step=100, value=500, label="home price (thousands)"
    )
    down_payment_pct = mo.ui.number(
        0, 100, step=5, value=20, label="down payment (%)"
    )
    rate = mo.ui.number(1.0, 8.0, step=0.25, value=5.0, label="interest rate (%)")
    years = mo.ui.number(5, 45, step=1, value=30, label="mortgage term (years)")
    property_tax_rate = mo.ui.number(
        1, 10, step=0.25, value=1.25, label="property tax (%)"
    )
    utilities = mo.ui.number(100, 1000, value=500, label="utilities monthly ($)")
    home_insurance = mo.ui.number(
        100, 1000, value=150, label="home insurance monthly ($)"
    )

    home_purchase_parameters = [home_price, down_payment_pct, rate, years]
    home_expense_parameters = [
        property_tax_rate,
        utilities,
        home_insurance,
    ]

    mo.md(
        f"""
        ## Loan

        Next, enter some details about the home you'd like to purchase,
        the mortgage you qualify for, and additional home expenses.
        """
    )
    return (
        down_payment_pct,
        home_expense_parameters,
        home_insurance,
        home_price,
        home_purchase_parameters,
        property_tax_rate,
        rate,
        utilities,
        years,
    )


@app.cell
def __(home_expense_parameters, home_purchase_parameters, mo):
    mo.hstack([home_purchase_parameters, home_expense_parameters])
    return


@app.cell
def __(down_payment_pct, home_price, mortgage, rate, years):
    down_payment = down_payment_pct.value / 100 * home_price.value
    principal = home_price.value - down_payment

    loan = mortgage.Loan(
        principal=principal * 1e3, interest=rate.value / 100, term=years.value
    )
    return down_payment, loan, principal


@app.cell
def __(
    down_payment,
    home_insurance,
    home_price,
    loan,
    mo,
    net_cash,
    net_cash_per_month,
    property_tax_rate,
    rate,
    utilities,
):
    property_tax_monthly = (
        property_tax_rate.value / 100 * home_price.value * 1e3 / 12
    )
    home_insurance_monthly = home_insurance.value
    mortgage_monthly = float(loan.monthly_payment)
    utilities_monthly = utilities.value

    monthly_home_payment = (
        property_tax_monthly
        + home_insurance_monthly
        + mortgage_monthly
        + utilities_monthly
    )

    annual_home_payment = monthly_home_payment * 12
    cash_less_housing = net_cash - annual_home_payment

    mo.md(
        f"""
        You're purchasing a home worth **\${home_price.value * 1000:,}**, with a 
        down payment of **\${down_payment*1000:,.02f}**.
        
        At a rate of **{rate.value}**%,
        you will owe **\${annual_home_payment:,.02f}** per year on home expenses.
        That's **\${monthly_home_payment:,.02f}** per month, which is
        **{monthly_home_payment / (net_cash_per_month) * 100:,.02f}%** of
        your take-home pay.
        
        You'll have **\${cash_less_housing/12:,.02f}** left over per 
        month for expenses and saving.
          """
    ).callout()
    return (
        annual_home_payment,
        cash_less_housing,
        home_insurance_monthly,
        monthly_home_payment,
        mortgage_monthly,
        property_tax_monthly,
        utilities_monthly,
    )


@app.cell
def __(mo):
    mo.md("## Monthly Expenses")
    return


@app.cell
def __(mo):
    mo.md(
        """
        In addition to paying for your home, you'll have monthly expenses on
        necessities and entertainment. Let's estimate these to see how much
        you'll save per month, after all expenses.
        """
    )
    return


@app.cell
def __(mo):
    vacation = mo.ui.number(0, 100000, step=100, value=100)
    groceries = mo.ui.number(0, 100000, step=100, value=100)
    dining_out = mo.ui.number(0, 100000, step=100, value=100)
    gifts = mo.ui.number(0, 100000, step=100, value=100)
    car_payment = mo.ui.number(0, 100000, step=100, value=100)
    entertainment = mo.ui.number(0, 100000, value=100)
    clothing = mo.ui.number(0, 100000, value=100)
    misc = mo.ui.number(0, 100000, step=100, value=100)
    return (
        car_payment,
        clothing,
        dining_out,
        entertainment,
        gifts,
        groceries,
        misc,
        vacation,
    )


@app.cell
def __(
    car_payment,
    clothing,
    dining_out,
    entertainment,
    gifts,
    groceries,
    misc,
    mo,
    vacation,
):
    def _row(kind, control):
        return {"Expense": kind, "Amount ($)": control}


    mo.ui.table(
        [
            _row("groceries", groceries),
            _row("dining out", dining_out),
            _row("gifts", gifts),
            _row("car payment", car_payment),
            _row("entertainment", entertainment),
            _row("clothing", clothing),
            _row("vacation", vacation),
            _row("miscellaneous", misc),
        ]
    )
    return


@app.cell
def __(
    car_payment,
    cash_less_housing,
    clothing,
    dining_out,
    entertainment,
    gifts,
    groceries,
    misc,
    mo,
    vacation,
):
    monthly_expenses = (
        groceries.value
        + dining_out.value
        + gifts.value
        + car_payment.value
        + entertainment.value
        + clothing.value
        + vacation.value
        + misc.value
    )

    annual_cash_saved = cash_less_housing - monthly_expenses * 12

    mo.md(
        f"""
        Your total monthly expenses are **\${monthly_expenses:,.02f}**.

        This means you will save **\${annual_cash_saved/12:,.02f}** per month,
        or **\${annual_cash_saved:,.02f}** annually.
        """
    )
    return annual_cash_saved, monthly_expenses


@app.cell
def __(loan):
    schedule = loan.schedule()[1:]
    return schedule,


@app.cell
def __(np, schedule):
    _interest, _principal = zip(
        *[(payment.interest, payment.principal) for payment in schedule]
    )

    interest_payments = np.array(_interest)
    principal_payments = np.array(_principal)
    return interest_payments, principal_payments


@app.cell
def __(interest_payments, mo, np, principal_payments, years):
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(1, 2)
    fig.set_size_inches(9, 3)

    _cum_interest = np.cumsum(interest_payments)
    _cum_principal = np.cumsum(principal_payments)

    axs[0].plot(_cum_interest, label="interest")
    axs[0].plot(_cum_principal, label="principal")
    axs[0].plot(_cum_interest + _cum_principal, label="total")

    for _year in range(5, years.value, 5):
        axs[1].axvline(_year * 12, linestyle="--", color="lightgray")

    axs[0].legend()
    axs[0].set_title("Cumulative")
    axs[0].set_xlabel("Months")

    axs[1].plot(interest_payments, label="interest")
    axs[1].plot(principal_payments, label="principal")
    axs[1].plot(interest_payments + principal_payments, label="total")
    for _year in range(5, years.value, 5):
        axs[1].axvline(_year * 12, linestyle="--", color="lightgray")
    axs[1].set_title("Monthly")
    axs[1].legend()
    axs[1].set_xlabel("Months")
    plt.tight_layout()

    mo.md(
        f"""
        ## Payments

        The plots below visualize your mortgage payments, over the duration of the
        entire mortgage. The left plot shows cumulative payments, and the right one
        shows monthly payments.
        
        {mo.as_html(fig)}
        """
    )
    return axs, fig, plt


@app.cell
def __():
    import marimo as mo
    import mortgage
    import numpy as np
    return mo, mortgage, np


if __name__ == "__main__":
    app.run()
