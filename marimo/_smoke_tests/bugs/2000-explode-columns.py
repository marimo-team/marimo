import marimo

__generated_with = "0.8.0"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def __(pd):
    list_data = [['meow1', 'meow2'], ['meow1', 'meow2', 'meow3'], 'meow', ['a', 'b', 'c'], 'meow']
    json_data = [
        {'acol': 'acol1', 'bcol': 'bcol1'},
        {'acol': 'acol2', 'bcol': 'bcol2'},
        {'acol': 'acol3', 'bcol': 'bcol3'},
        {'acol': 'acol4', 'bcol': 'bcol4'},
        {'acol': 'acol5', 'bcol': 'bcol5'}
    ]
    df = pd.DataFrame()
    df['list_data'] = list_data
    df['json_data'] = json_data
    df2 = df.copy(deep=True)
    df
    return df, df2, json_data, list_data


@app.cell
def __(mo):
    mo.md("""### Transformations performed manually with pandas:""")
    return


@app.cell
def __(df, pd):
    df3 = df.copy(deep=True)
    df3 = df.join(pd.DataFrame(df.pop('json_data').values.tolist()))
    df3.explode('list_data')
    return df3,


@app.cell(hide_code=True)
def __(mo):
    mo.md("""### Transformations performed using `mo.ui.dataframe`:""")
    return


@app.cell
def __(df2, mo):
    mo.ui.dataframe(df2[['list_data', 'json_data']])
    return


if __name__ == "__main__":
    app.run()
