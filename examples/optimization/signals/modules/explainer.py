from typing import Optional

from . import components


LIB = components.Components


def explainer(component: str) -> Optional[str]:
    explainers = {
        LIB.ASYMMETRIC_SMALL: (
            f"""
            The **{component}** creates a component that treats values
            bigger and smaller than the component mean asymetrically. It's
            often used as a residual component class. Use the threshold
            parameter to control the trade-off between positive and negative
            values (or, when building a multiplicative decomposition, between
            values greater than and less than 1).
            """
        ),
        LIB.UNIFORMLY_SMALL: (
            f"""
            The **{component}** class creates a component that is encouraged
            to be small, uniformly through time. It's often used as a residual
            component class.
            """
        ),
        LIB.SPARSE_SMALL: (
            f"""
            The **{component}** class creates a component that is encouraged
            to be small, with only a few non-zero entries but possible with some
            entries that are somewhat not small. It's often used as a residual
            component class."""
        ),
        LIB.AGGREGATE: (
            f"""
            The **{component}** class is a special class that wraps other
            component classes, creating a component that tries to have
            the properties of all its wrapped classes. For example,
            an aggregate of a Periodic and an Average Equal class
            creates a periodic component centered around a specific number,
            while an aggregate of a Periodic and Trend-line class creates
            a periodic component that varies smoothly.
            """
        ),
        LIB.AVERAGE_EQUAL: (
            f"""
            The **{component}** class creates a component that has a given
            average value (which you specifiy). Typically used as part of
            an aggregate.
            """
        ),
        LIB.CONSTANT: (
            f"""
            The **{component}** class creates a component that has a constant
            value.
            """
        ),
        LIB.FIRST_VALUE_FIXED: (
            f"""
            The **{component}** creates a component that has a given first
            value (which you specify). Typically used as part of an aggregate.
            """
        ),
        LIB.TREND_LINE: (
            f"""
            The **{component}** class create a component that has no curvature
            at all. It's useful if you want to extract a linear trend.
            """
        ),
        LIB.PIECEWISE_CONSTANT: (
            f"""
            The **{component}** creates a component that is mostly constant,
            but possibly with a few jumps. It's useful to detect
            abrupt changes.
            """
        ),
        LIB.PERIODIC: (
            f"""
            The **{component}** class creates components that repeat 
            themselves
            after a number of time-steps that you choose. It's useful
            for signals with seasonal or daily patterns.
            """
        ),
        LIB.SMOOTH: (
            f"""
            The **{component}** class creates a component that is encouraged
            vary smoothly, without large swings in value.  This is useful
            if you think your signal doesn't have large fluctuations.
            """
        ),
    }

    return explainers[component] if component in explainers else None
