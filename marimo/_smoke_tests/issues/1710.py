# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    import keras
    model = keras.models.Sequential()
    model.add(keras.layers.Input(shape=(1,)))
    model.add(keras.layers.Dense(2, activation='relu'))
    model.add(keras.layers.Dense(1, activation='sigmoid'))
    keras.utils.plot_model(model)
    return


if __name__ == "__main__":
    app.run()
