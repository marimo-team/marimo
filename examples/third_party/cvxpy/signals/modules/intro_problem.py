from typing import cast

import gfosd
import numpy as np
from gfosd import components as gfc

from . import problems
from . import components as complib


def _plot_empty(width, height, xlim, ylim):
    return problems.plot_line(
        x=None,
        y=None,
        x_label=" ",
        y_label=" ",
        title=" ",
        width=width,
        height=height,
        xlim=xlim,
        ylim=ylim,
    )


def generate_synthetic_data(seed=42, samples=100):
    class Data:
        time: np.ndarray
        signal: np.ndarray

    np.random.seed(seed)
    t = np.linspace(0, 1000, samples)
    sine_wave = 1.5 * np.sin(2 * np.pi * t * 1 / (500.0))
    trend = np.linspace(0, 10, samples)
    noise = 0.1 * np.random.randn(len(sine_wave))
    X = np.vstack([sine_wave, noise, trend])
    data = Data()
    data.time = t
    data.signal = X.sum(axis=0)
    return data


class IntroProblem:
    def __init__(self, seed=42):
        self.data = generate_synthetic_data(seed=seed)
        self.options = {
            complib.Components.TREND_LINE: gfc.NoCurvature(),
            complib.Components.PERIODIC: gfc.Periodic(
                period=self.data.time.shape[0] // 2
            ),
            complib.Components.PIECEWISE_CONSTANT: gfc.SumCard(
                diff=1,
                weight=2,
            ),
        }

    def plot(self):
        return problems.plot_line(
            self.data.time,
            self.data.signal,
            x_label="time",
            y_label="measurement",
        )

    def plot_decomp(self, components, min_plots, width=210, height=210):
        xrange = [0, 1000]
        yrange = [-4, 12]
        if not components:
            return [
                _plot_empty(
                    width=width,
                    height=height,
                    xlim=xrange,
                    ylim=yrange,
                )
            ] * min_plots
        else:
            component_classes = [self.options[c] for c in components]
            names = [
                f"Noise Component: {complib.Components.UNIFORMLY_SMALL}",
                *components,
            ]
            c = [gfc.SumSquare(weight=1e-2), *component_classes]
            problem = gfosd.Problem(self.data.signal, c)
            problem.decompose(verbose=False)
            decomposition = cast(np.ndarray, problem.decomposition)
            plots = []
            for i in range(decomposition.shape[0]):
                plots.append(
                    problems.plot_line(
                        x=self.data.time,
                        y=decomposition[i, :],
                        width=width,
                        height=height,
                        xlim=xrange,
                        ylim=yrange,
                        title=f"{names[i]}",
                    )
                )
            if len(plots) < min_plots:
                plots.append(_plot_empty(width, height, xrange, yrange))
            return plots
