from __future__ import annotations

import abc
from typing import Optional, cast

import gfosd.components as gfc
import matplotlib
import matplotlib.pyplot as plt
import marimo as mo
import numpy as np

from . import components as componentlib
from . import dataloaders
from . import layout
from . import solutions
from gfosd import Problem
from sklearn.preprocessing import MinMaxScaler

clib = componentlib.Components
plib = componentlib.Parameters


def configure_matplotlib(font_size=10):
    params = {
        "axes.labelsize": font_size,
        "axes.titlesize": font_size,
        "font.size": font_size,
        "legend.fontsize": font_size,
        "xtick.labelsize": font_size,
        "ytick.labelsize": font_size,
        "font.family": "sans serif",
    }
    matplotlib.rcParams.update(params)


def plot_line(
    x,
    y,
    x_label=None,
    y_label=None,
    title=None,
    color=None,
    width=6.4,
    height=2.5,
    xlim=None,
    ylim=None,
    ax=None,
):
    if ax is None:
        plt.figure(figsize=(width, height))
        ax = cast(plt.Axes, plt.gca())
    if x is not None and y is not None:
        ax.plot(x, y, color=color)
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    return ax


class OSDProblem(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def name() -> str:
        pass

    # TODO returns mo.Html, or at least html showable ...
    @abc.abstractmethod
    def description(self):
        pass

    @abc.abstractmethod
    def plot_signal(self, ax: Optional[plt.Axes] = None) -> plt.Axes:
        pass

    @abc.abstractmethod
    def decompose(self, components):
        pass

    @abc.abstractmethod
    def feedback(self, components, parameters):
        pass


class MaunaLoa(OSDProblem):
    def __init__(self):
        self.df = dataloaders.get_c02_data()

    @staticmethod
    def name() -> str:
        return "Mauna Loa Observatory: Carbon Dioxide Emissions"

    def description(self):
        return mo.md(
            f"""
            Let's look at a signal that's very relevant to us today:
            atmospheric CO~2~ levels from May 1974 through June 2021, measured
            at Mauna Loa, Hawaii. Here's the signal:

            {mo.as_html(self.plot_signal()).center()}
            
            Because of climate change, we expect emissions to increase with
            time, and they do. But we also see that the signal has seasonal
            fluctuations, and probably some noise.

            **Your task**: Build a decomposition that isolates the long-term
            trend from the seasonal fluctuation.
            """
        )

    def plot_signal(self, ax: Optional[plt.Axes] = None) -> plt.Axes:
        return plot_line(
            self.df["decimal"],
            self.df["average"],
            x_label="Year",
            y_label="Average Emissions (ppm)",
            ax=ax,
        )

    def decompose(self, components):
        problem = Problem(
            data=self.df["average"].values, components=components
        )
        problem.decompose(verbose=False, max_iter=1000)
        return problem.plot_decomposition()

    def feedback(self, components: list[componentlib.Components], params):
        if components[0] == clib.UNIFORMLY_SMALL and set(
            components[1:]
        ) == set([clib.SMOOTH, clib.PERIODIC]):
            for c, p in zip(components[1:], params[1:]):
                if c == clib.PERIODIC and p[plib.PERIOD] == 53:
                    return mo.md(
                        """
                        🎉 **You did it!**

                        You just made a "seasonal-trend decomposition".
                        The "Denoised Signal" plotted below is the sum of
                        your components, excluding the noise component;
                        it's an idealized or cleaned-up version of the
                        data that captures the seasonality and trend.

                        Seasonal-trend decompositions are widely used
                        in weather and evironment-related applications,
                        as well as in economics.
                        """
                    ).callout(kind="success")
                elif c == clib.PERIODIC and p[plib.PERIOD] == 52:
                    return mo.md(
                        """
                        So close!

                        Hint: No year has exactly 52 weeks.
                        """
                    ).callout(kind="alert")

            return mo.md(
                """
                Almost! But your period isn't quite right. How long, in weeks,
                do you expect each seasonal cycle to last?
                """
            ).callout(kind="alert")
        elif (
            len(components) == 3
            and clib.SMOOTH in components
            and clib.PERIODIC in components
        ):
            return mo.md(
                """
                Almost there!

                Hint: The first component (which always represents noise)
                should resemble small random error left-over from the
                decomposition.
                """
            ).callout(kind="alert")
        elif len(components) > 3:
            return mo.md(
                """
                Not quite there. Hint: You only need 3 components for
                a seasonal-trend decomposition.
                """
            ).callout(kind="alert")
        elif len(components) >= 1:
            return mo.md(
                """
                Nice job getting started. Keep experimenting.
                """
            ).callout()


class SolarPower(OSDProblem):
    def __init__(self):
        self.df = dataloaders.get_pvdaq_data()
        self._preprocessed_signal = solutions._preprocess_pvdaq(self.df)

    @staticmethod
    def name() -> str:
        return "National Renewable Energy Lab: Solar Power Generation"

    def description(self):
        product_callout = mo.md(
            """
            In this decomposition, the _product_ of the components will equal 
             the original signal, not the sum. We achieve this by taking 
             logs of the data before computing the decomposition, 
             and exponentiating it after. A multiplicative decomposition is 
             more interpretable for this example (why?).
            """
        ).callout(kind="alert")

        return mo.md(
            f"""
            This signal measures DC power generated by a collection of solar
            panels. (The data was provided by the National Renewable Energy
            Laboratory.) Shown below is two week's worth of data, from Jan. 1
            through Jan. 14 2011, sampled every 15 minutes. Each peak represents
            the max DC power generation for a given day.

            {mo.as_html(self.plot_signal())}


            The signal roughly repeats every day (which equals 96 15-minute
            periods), though there is slight to sometimes considerable variance in
            the amount of power generated on each day.

            **Your task**: Create a decomposition that captures the gross daily
            pattern of the power generation and also captures generation
            performance at any point in time as a fraction of typical performance.
            Aim for typical performance of 90,000, ie, peaks of roughly 90,000
            in the period component. You'll only need two components.


            {product_callout}
            """
        )

    def decompose(self, components):
        problem = Problem(
            data=self._preprocessed_signal, components=components
        )
        problem.decompose(verbose=False, max_iter=2000)
        return problem.plot_decomposition(exponentiate=True)

    def plot_signal(self, ax: Optional[plt.Axes] = None) -> plt.Axes:
        subdf = self.df.loc[:"2011-01-14"]
        y = subdf["dc_power"].values
        ax = plot_line(
            x=np.arange(y.size),
            y=y,
            x_label="Samples (every 15 minutes)",
            y_label="DC Power",
            ax=ax,
        )
        plt.tight_layout()
        return ax

    def feedback(self, components, params):
        if components == [clib.ASYMMETRIC_SMALL, clib.PERIODIC]:
            if params[0][plib.THRESHOLD] < 0.8:
                return mo.md(
                    f"""
                    Nice! A **{clib.ASYMMETRIC_SMALL}** component might be
                    useful. Try adjusting the threshold parameter. Remember
                    that in this example, noise represents deviations
                    from clear-sky power generation.
                    """
                ).callout(kind="alert")
            if params[1][plib.PERIOD] != 96:
                return mo.md(
                    """
                    Almost there! What should the period be?
                    """
                ).callout(kind="alert")
            return mo.md(
                f"""
                🎉 **You did it!**

                You just made a multiplicative model of real data. Your
                model captures the average daily pattern of solar panel
                generation.

                You used the **{clib.ASYMMETRIC_SMALL}** component class to
                explain when the data deviates from that pattern, and by how
                much. By choosing a large threshold, you chose to build a
                decomposition that emphasizes the "clear-sky" power generation,
                with the noise component representing weather events that
                decrease the power generated.

                **Just for fun:** Try replacing a Periodic component
                with an **{clib.AGGREGATE}** of a **{clib.PERIODIC} component**
                and a **{clib.SMOOTH}** component: you should find that this
                smooths out the jagged features that are currently in your
                Periodic component.
                """
            ).callout(kind="success")
        elif components == [clib.ASYMMETRIC_SMALL, clib.AGGREGATE]:
            if params[0][plib.THRESHOLD] < 0.8:
                return mo.md(
                    f"""
                    Nice! A {clib.ASYMMETRIC_SMALL} component might be useful.
                    Try adjusting the threshold parameter.
                    """
                ).callout(kind="alert")
            if params[1][plib.COMPONENTS] == 2:
                child_components = list(c for c, _ in params[1][plib.CHILDREN])
                if set(child_components) == set((clib.SMOOTH, clib.PERIODIC)):
                    child_params = list(p for _, p in params[1][plib.CHILDREN])
                    periodic_index = (
                        0 if child_components[0] == clib.PERIODIC else 1
                    )
                    if (
                        child_params[periodic_index][plib.PERIOD] == 96
                        and child_params[(periodic_index + 1) % 2][plib.WEIGHT]
                        >= 1
                    ):
                        return mo.md(
                            """
                            🎉 **Wow!**

                            That's a pretty advanced decomposition you just made.
                            """
                        ).callout(kind="success")
            return mo.md(
                f"""
                Almost there! Use **{clib.PERIODIC}** (use period = 96) and
                 **{clib.SMOOTH}** (use weight = 1) child components for your
                 aggregate.
                """
            ).callout(kind="alert")
        elif components[0] != clib.ASYMMETRIC_SMALL:
            return mo.md(
                """
                Hint: Try a different noise component. This component should
                capture when power generation degrades.
                """
            ).callout(kind="alert")
        elif len(components) > 2:
            return mo.md(
                """
                You only need two components.
                """
            ).callout(kind="alert")
        elif len(components) >= 1:
            return mo.md(
                """
                Nice job getting started. Keep experimenting.
                """
            ).callout()


class ChangePoint(OSDProblem):
    def __init__(self):
        self.y, self.X = dataloaders.make_changepoint_data()

    @staticmethod
    def name() -> str:
        return "Change Point Detection"

    def description(self):
        return mo.md(
            f"""
            This synthetic signal has a few abrupt changes in it, at time-steps
            400, 600, 700, 800, and 900.

            {mo.as_html(self.plot_signal())}

            **Your task:** Create a decomposition that isolates the changes.
            """
        )

    def decompose(self, components):
        problem = Problem(data=self.y, components=components)
        problem.decompose(verbose=False, max_iter=1000)
        return problem.plot_decomposition()

    def plot_signal(self, ax: Optional[plt.Axes] = None) -> plt.Axes:
        return plot_line(
            np.arange(self.y.size),
            self.y,
            x_label="Time",
            y_label="Measurement",
            ax=ax,
        )

    def feedback(self, components, parameters):
        if components[1] == clib.PIECEWISE_CONSTANT:
            if parameters[1][plib.WEIGHT] == 1:
                return mo.md(
                    f"""
                    🎉 **You did it!**

                    You just deteced some change points. Every time the non-noise
                    component jumps is a change point. (If the component doesn't
                    look piecewise-constant, you may need to adjust the weights.)

                    Change point detection is a very old problem with applications
                    in many fields, including in photovoltaic systems, medicine,
                    finance, and others. Change point detection can be a very
                    challenging problem, and is intractable in general. That said,
                    signal decomposition can be a very good heuristic for it.
                    """
                ).callout(kind="success")
            else:
                return mo.md(
                    f"""
                    So close! Try adjusting the weight of the
                    **{clib.PIECEWISE_CONSTANT}** component.
                    """
                ).callout(kind="alert")
        elif len(components) >= 3:
            return mo.md(
                """
                Hint: You only need two components.
                """
            ).callout(kind="alert")
        elif len(components) >= 1:
            return mo.md(
                """
                Nice job getting started. Keep experimenting.
                """
            ).callout()
        else:
            return None


class Soiling(OSDProblem):
    def __init__(self):
        self.df, _ = dataloaders.make_soiling_data()
        y0 = self.df["daily_norm"].values.copy()
        y1 = np.log(y0)
        prescaling = MinMaxScaler(feature_range=(0, 10))
        y2 = prescaling.fit_transform(y1.reshape(-1, 1)).ravel()
        self.y = y2

    @staticmethod
    def name() -> str:
        return "Solar Panel Soiling"

    def description(self):
        reference_decomposition = layout.image(
            "assets/solar_power_soiling_reference.png"
        )
        return mo.md(
            f"""
            This signal represents generation efficiency of an array
            of solar panels. Solar panel performance decreases with time, as
            dust and other particulates collect on the panels, blocking
            sunlight. This degradation is known as 'soiling loss'.

            {mo.as_html(self.plot_signal())}

            This is a synthetic signal, but it captures some key
            characteristics. The power generation

            - is noisy
            - osciallates around a constant average efficiency
            - slowly degrades linearly over the years
            - has a periodic component with a period of 365 days
            - degrades and recover as panels are soiled and cleaned

            We've created what we think is a good decomposition for this
            data. Here it is:

            {mo.tree([reference_decomposition], label="reference decomposition")}

            **Your task:** Create a decomposition that matches our reference
            decomposition.

            {
            mo.md(
                '''
                Hint: There are many different decompositions that can capture
                 the signal's key characteristics. Unlike the previous
                 examples, this one doesn't really have a "right" answer, so we
                 won't give you any feedback on your choices. Just try your
                 best to match our decomposition using what you've learned so
                 far, and have fun!
                '''
            ).callout()
            }
            """
        )

    def decompose(self, components):
        problem = Problem(data=self.y, components=components)
        problem.decompose(verbose=False, max_iter=1000)
        f = problem.plot_decomposition()
        for i, component in enumerate(components):
            if isinstance(component, gfc.NoSlope):
                avg = np.average(problem.decomposition[i])
                f.axes[i].set_ylim(avg - 2.5, avg + 2.5)
                break
        return f

    def plot_signal(self, ax: Optional[plt.Axes] = None) -> plt.Axes:
        ax = plot_line(
            x=self.df.index,
            y=self.y,
            x_label="Year",
            y_label="Power Generation",
        )
        ax.set_title("Solar Panel Generation, with Soiling")
        return ax

    def feedback(self):
        raise NotImplementedError


class CustomDataProblem(abc.ABC):
    def __init__(self, signal, title):
        self.signal = signal
        self.title = title

    @staticmethod
    def name() -> str:
        return "Upload Your Own Signal"

    def description(self):
        return mo.md(
            f"""
            Here is a plot of the signal you uploaded.

            {mo.as_html(self.plot_signal())}
            """
        )

    def plot_signal(self, ax: Optional[plt.Axes] = None) -> plt.Axes:
        ax = plot_line(
            x=np.arange(self.signal.size),
            y=self.signal,
            ax=ax,
        )
        ax.set_title(self.title)
        return ax

    def decompose(self, components):
        problem = Problem(data=self.signal, components=components)
        problem.decompose(verbose=False, max_iter=1000)
        return problem.plot_decomposition()

    def feedback(self, components, parameters):
        del components
        del parameters
        return None
