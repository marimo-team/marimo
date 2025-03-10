import marimo

__generated_with = "0.6.19"
app = marimo.App()


with app.setup:
    y = 1
    x = 0
    y = y / x


if __name__ == "__main__":
    app.run()
