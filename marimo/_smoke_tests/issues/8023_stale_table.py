import marimo
app = marimo.App()

@app.cell
def _():
    import marimo as mo
    import pandas as pd
    return mo, pd

@app.cell
def _(mo):
    data_version, set_data_version = mo.state(0)
    return data_version, set_data_version

@app.cell
def _():
    data = [
        {"id": 1, "status": "pending", "value": 10},
        {"id": 2, "status": "pending", "value": 20},
        {"id": 3, "status": "pending", "value": 30},
        {"id": 4, "status": "pending", "value": 40},
    ]
    return (data,)

@app.cell
def _(data, data_version, mo, pd):
    _ = data_version()
    df = pd.DataFrame(data)
    table = mo.ui.table(df, selection="single", page_size=3)
    mo.output.replace(table)
    return (table,)

@app.cell
def _(mo):
    approve_btn = mo.ui.run_button(label="Approve")
    mo.output.replace(approve_btn)
    return (approve_btn,)

@app.cell
def _(approve_btn, data, set_data_version, table):
    import time
    if approve_btn.value:
        _sel = table.value
        if _sel is not None and len(_sel) > 0:
            _id = _sel.iloc[0]["id"]
            for item in data:
                if item["id"] == _id:
                    item["status"] = "approved"
                    break
            set_data_version(time.time())
    return

if __name__ == "__main__":
    app.run()
