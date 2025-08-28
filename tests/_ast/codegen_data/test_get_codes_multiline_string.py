import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def one(): c = """
  a, b"""; return (c,)


@app.cell
def two():
    d = """
a, b"""
    # comment
    return (d,)

if __name__ == "__main__":
    app.run()
