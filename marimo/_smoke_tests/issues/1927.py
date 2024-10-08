# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.14"
app = marimo.App(width="medium")


@app.cell
def __():
    breaker = []
    for i in range(5):
        breaker.append(breaker)
    breaker
    return breaker, i


if __name__ == "__main__":
    app.run()
