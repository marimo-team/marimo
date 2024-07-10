# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.25"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import os
    import keras
    model = keras.models.Sequential()
    model.add(keras.layers.Input(shape=(1,)))
    model.add(keras.layers.Dense(2, activation='relu'))
    model.add(keras.layers.Dense(1, activation='sigmoid'))
    keras.utils.plot_model(model)
    return keras, mo, model, os


if __name__ == "__main__":
    app.run()
