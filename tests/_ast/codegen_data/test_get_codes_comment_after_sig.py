import marimo

__generated_with = '0.1.0'
app = marimo.App()


@app.cell
def one(): # comment
    print("hi")
    return


if __name__ == "__main__":
    app.run()
