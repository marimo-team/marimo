

import marimo

__generated_with = "0.8.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import datetime
    return datetime, mo


@app.cell
def __():
    initial_data = [{"x": 1, "y": -1}]
    return initial_data,


@app.cell
def __(initial_data, mo):
    get_data, set_data = mo.state(initial_data)
    return get_data, set_data


@app.cell
def __(datetime, get_data, mo, set_data):
    _data = get_data()
    print("Creating new table list", datetime.datetime.utcnow())
    def on_change_wrapper(i, k):    
        def on_change(value):
            print("setting")
            _data = get_data()
            _data[i][k] = value
            set_data(_data)
        return on_change

    table_list = [{k: mo.ui.number(value=v, start=-100, stop=100, on_change=on_change_wrapper(i, k)) for k, v in d.items()} for i, d in enumerate(_data)]
    return on_change_wrapper, table_list


@app.cell
def __(mo, table_list):
    table = mo.ui.table(table_list)
    return table,


@app.cell
def __(get_data, mo, set_data):
    def on_click(*value):
        rows = get_data()
        rows.append({"x": 0, "y": 0})
        set_data(rows)



    add_row = mo.ui.button(label="add row", on_click=on_click)
    return add_row, on_click


@app.cell
def __(add_row, mo, table):
    mo.vstack([table, add_row])
    return


@app.cell
def __(get_data):
    get_data()
    return


@app.cell
def __(table_list):
    table_list[0]["x"].value
    return


if __name__ == "__main__":
    app.run()
