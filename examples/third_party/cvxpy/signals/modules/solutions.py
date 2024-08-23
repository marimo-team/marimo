from __future__ import annotations

from typing import Tuple

import gfosd.components as comp
import numpy as np
import numpy.typing as npt
import pandas as pd
from gfosd import Problem
from sklearn.preprocessing import MinMaxScaler


def co2_problem(co2_dataframe) -> Problem:
    return Problem(
        data=co2_dataframe["average"].values,
        components=[
            comp.SumSquare(weight=1 / len(co2_dataframe)),
            comp.SumSquare(diff=1, weight=1e-2),
            comp.Aggregate(
                [comp.Periodic(period=53), comp.AverageEqual(0, period=53)]
            ),
        ],
    )


def _preprocess_pvdaq(pv_dataframe) -> np.ndarray:
    # data preprocessing
    y0 = pv_dataframe.loc[:"2011-01-14", "dc_power"].values.copy()
    # take log
    y1 = np.ones_like(y0) * np.nan
    y1[y0 > 0] = np.log(y0[y0 > 0])
    return y1


def pvdaq_problem(pv_dataframe) -> Problem:
    period = pv_dataframe.loc[:"2011-01-15", "dc_power"].values.shape[0] // 15
    ss_y = _preprocess_pvdaq(pv_dataframe)
    pv_problem = Problem(
        data=ss_y,
        components=[
            comp.SumQuantile(weight=1 / len(pv_dataframe), tau=0.85),
            comp.Aggregate(
                [
                    comp.SumSquare(diff=2, weight=1e-2),
                    comp.Periodic(period=period),
                ]
            ),
        ],
    )
    return pv_problem


def basic_changepoint_problem_exact(signal) -> Problem:
    c1 = comp.SumSquare(weight=1 / len(signal))
    c2 = comp.SumCard(weight=1e-3, diff=1)
    return Problem(signal, [c1, c2])


def basic_changepoint_problem_heuristic(signal) -> Problem:
    c1 = comp.SumSquare(weight=1 / len(signal))
    c2 = comp.SumAbs(weight=1e-3, diff=1)
    return Problem(signal, [c1, c2])


def hard_changepoint_problem(signal) -> Problem:
    return Problem(
        signal,
        [
            comp.SumSquare(weight=1 / len(signal)),
            comp.SumCard(weight=1e-3, diff=1),
            comp.Aggregate(
                [
                    comp.SumSquare(weight=1e2, diff=2),
                    comp.Periodic(period=400),
                    comp.AverageEqual(0, period=400),
                ]
            ),
        ],
    )


def soiling_problem(ss_df: pd.DataFrame) -> Tuple[Problem, npt.NDArray]:
    # data preprocessing
    _y0 = ss_df["daily_norm"].values.copy()
    _y1 = np.log(_y0)
    prescaling = MinMaxScaler(feature_range=(0, 10))
    _y2 = prescaling.fit_transform(_y1.reshape(-1, 1)).ravel()
    ss_y = _y2

    # residual component
    c1 = comp.SumSquare(weight=1 / len(ss_y))
    # constant component
    c2 = comp.NoSlope()
    # linear degradation component
    c3 = comp.Aggregate([comp.NoCurvature(), comp.FirstValEqual(0)])
    # seasonal baseline component
    c4 = comp.Aggregate(
        [
            comp.SumSquare(weight=5e0, diff=2),
            comp.Periodic(365),
            comp.AverageEqual(0, period=365),
        ]
    )
    # soiling component
    c5 = comp.Aggregate(
        [
            comp.Inequality(vmax=0),
            comp.SumAbs(weight=1e-5),
            comp.SumQuantile(weight=1e-5, diff=1, tau=0.9),
            comp.SumAbs(weight=5e-3, diff=2),
        ]
    )

    ss_problem = Problem(data=ss_y, components=[c1, c2, c3, c4, c5])
    ss_problem.decompose()

    # real signal
    xr = ss_df[["noise", "degradation", "seasonality", "soiling"]]
    xr.insert(1, "bias", np.ones(len(ss_df)))
    xr = np.log(xr.values.T)
    xr[0] *= prescaling.scale_
    xr[1] = prescaling.transform(xr[1].reshape(-1, 1)).ravel()
    xr[2:] *= prescaling.scale_
    return ss_problem, xr
