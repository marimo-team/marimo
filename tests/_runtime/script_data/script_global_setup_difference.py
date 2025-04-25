import marimo

__generated_with = "0.12.5"
app = marimo.App(width="medium")

injected = 100

with app.setup:
    print("*")
    if globals().get("injected", None) is None:
        injected = 0
    globals()["injected"] = globals().get("injected", 1) + 1


@app.cell
def test_single_run():
    print(injected)


if __name__ == "__main__":
    app.run()
