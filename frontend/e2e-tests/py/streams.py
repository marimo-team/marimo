import marimo

__generated_with = "0.0.1"
app = marimo.App()


@app.cell
def __():
    import os
    return os,


@app.cell
def __():
    print('Hello, python!')
    return


@app.cell
def __(os):
    os.system('echo Hello, stdout!')
    os.system('echo Hello, stderr! 1>&2')
    return


if __name__ == "__main__":
    app.run()
