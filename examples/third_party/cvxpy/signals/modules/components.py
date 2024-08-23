from __future__ import annotations
from dataclasses import dataclass, fields

import marimo as mo
from gfosd import components as gfc


@dataclass
class Components:
    UNIFORMLY_SMALL: str = "Small, Uniformly"
    SPARSE_SMALL: str = "Small, Sparse"
    ASYMMETRIC_SMALL: str = "Small, Asymmetrically"
    SMOOTH: str = "Smooth"
    PERIODIC: str = "Periodic"
    PIECEWISE_CONSTANT: str = "Piecewise Constant"
    TREND_LINE: str = "Trend-line"
    AGGREGATE: str = "Aggregate"
    AVERAGE_EQUAL: str = "Average Equal"
    CONSTANT: str = "Constant"
    FIRST_VALUE_FIXED: str = "First Value Fixed"


@dataclass
class ResidualComponents:
    UNIFORMLY_SMALL: str = Components.UNIFORMLY_SMALL
    SPARSE_SMALL: str = Components.SPARSE_SMALL
    ASYMMETRIC_SMALL: str = Components.ASYMMETRIC_SMALL


def _sorted(collection) -> list:
    return list(sorted(collection))


RESIDUAL_COMPONENTS = _sorted([e.default for e in fields(ResidualComponents)])
COMPONENT_LIBRARY = _sorted([e.default for e in fields(Components)])


@dataclass
class Parameters:
    PERIOD: str = "period"
    WEIGHT: str = "weight"
    THRESHOLD: str = "threshold"
    COMPONENTS: str = "components"
    FIRST_VALUE: str = "first value"
    AVERAGE: str = "average"
    CHILDREN: str = "children"


PARAMETER_UNIVERSE = {
    Parameters.PERIOD: [Components.PERIODIC],
    Parameters.WEIGHT: [
        Components.SMOOTH,
        Components.PIECEWISE_CONSTANT,
    ],
    Parameters.THRESHOLD: [ResidualComponents.ASYMMETRIC_SMALL],
    Parameters.COMPONENTS: [Components.AGGREGATE],
    Parameters.FIRST_VALUE: [Components.FIRST_VALUE_FIXED],
    Parameters.AVERAGE: [Components.AVERAGE_EQUAL],
}

PARAMETER_DEFAULTS = {
    Parameters.PERIOD: [182, lambda v: mo.ui.slider(1, 365, step=1, value=v)],
    Parameters.WEIGHT: [0, lambda v: mo.ui.slider(-3, 3, value=v)],
    Parameters.THRESHOLD: [
        0.5,
        lambda v: mo.ui.slider(0, 1, step=0.05, value=v),
    ],
    Parameters.COMPONENTS: [2, lambda v: mo.ui.number(1, 5, step=1, value=v)],
    Parameters.FIRST_VALUE: [
        0,
        lambda v: mo.ui.number(-100, 100, step=1, value=v),
    ],
    Parameters.AVERAGE: [
        0,
        lambda v: mo.ui.number(-100, 100, step=1, value=v),
    ],
}


def parameter_controls(
    component: Components | ResidualComponents, default_values
) -> mo.ui.dictionary:
    params = {}
    for param in PARAMETER_UNIVERSE:
        if component in PARAMETER_UNIVERSE[param]:
            v, ctor = PARAMETER_DEFAULTS[param]
            try:
                v = default_values[param]
            except KeyError:
                pass
            params[param] = ctor(v)
    return mo.ui.dictionary(params, label=f"{component}")


def construct_component(name, parameters, center_periodic=False):
    if name == Components.UNIFORMLY_SMALL:
        return gfc.SumSquare(weight=1)
    elif name == Components.SPARSE_SMALL:
        return gfc.SumAbs(weight=1)
    elif name == Components.ASYMMETRIC_SMALL:
        return gfc.SumQuantile(weight=1, tau=parameters[Parameters.THRESHOLD])
    elif name == Components.SMOOTH:
        return gfc.SumSquare(
            diff=2, weight=10 ** parameters[Parameters.WEIGHT]
        )
    elif name == Components.PIECEWISE_CONSTANT:
        return gfc.SumAbs(diff=1, weight=10 ** parameters[Parameters.WEIGHT])
    elif name == Components.CONSTANT:
        return gfc.NoSlope()
    elif name == Components.PERIODIC:
        if center_periodic:
            return gfc.Aggregate(
                [
                    gfc.Periodic(period=parameters[Parameters.PERIOD]),
                    gfc.AverageEqual(0),
                ]
            )
        else:
            return gfc.Periodic(period=parameters[Parameters.PERIOD])
    elif name == Components.FIRST_VALUE_FIXED:
        return gfc.FirstValEqual(parameters[Parameters.FIRST_VALUE])
    elif name == Components.AVERAGE_EQUAL:
        return gfc.AverageEqual(parameters[Parameters.AVERAGE])
    elif name == Components.TREND_LINE:
        return gfc.NoCurvature()
    elif name == Components.AGGREGATE:
        components = [
            construct_component(name, params)
            for name, params in parameters[Parameters.CHILDREN]
        ]
        if components:
            return gfc.Aggregate(components)
        else:
            return None
    elif name is None:
        return None
    else:
        raise ValueError("Unknown component ", name)
