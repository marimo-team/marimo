import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def global_error():
    tickers = ["AAPL", "GOOGL"]
    global tickers  # 


@app.cell
def return_error(tickers):
    if tickers is not None:
        return tickers
    return


if __name__ == "__main__":
    app.run()
