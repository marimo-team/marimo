# Copyright 2024 Marimo. All rights reserved.
import importlib
import logging
from abc import ABC, abstractmethod
from typing import Literal

LOGGER = logging.getLogger(__name__)

Theme = Literal["light", "dark"]


class Themer(ABC):
    """
    A class that manages themes for a third-party package.
    """

    pkg_name: str

    @abstractmethod
    def handle(self, theme: Theme) -> None:
        """
        Apply the theme to the package.
        """


class PlotlyThemer(Themer):
    """
    A class that manages themes for Plotly.
    """

    pkg_name = "plotly"

    def handle(self, theme: Theme) -> None:
        """
        Apply the theme to Plotly.
        """
        import plotly.io as pio  # type: ignore

        pio.templates.default = (
            "plotly_dark" if theme == "dark" else "plotly_white"
        )


# class MatplotlibThemer(Themer):
#     """
#     A class that manages themes for Matplotlib.
#     """

#     pkg_name = "matplotlib"

#     def handle(self, theme: Theme) -> None:
#         """
#         Apply the theme to Matplotlib.
#         """
#         import matplotlib.pyplot as plt

#         # Apply the style globally
#         plt.style.use('dark_background' if theme == "dark" else 'default')


class AltairThemer(Themer):
    """
    A class that manages themes for Altair.
    """

    pkg_name = "altair"

    def handle(self, theme: Theme) -> None:
        """
        Apply the theme to Altair.
        """
        import altair as alt  # type: ignore

        alt.themes.enable("dark" if theme == "dark" else "default")  # type: ignore


# class SeabornThemer(Themer):
#     """
#     A class that manages themes for Seaborn.
#     """

#     pkg_name = "seaborn"

#     def handle(self, theme: Theme) -> None:
#         """
#         Apply the theme to Seaborn.
#         """
#         import seaborn as sns

#         if theme == "dark":
#             sns.set_style("darkgrid")
#             sns.set_palette("dark")
#         else:
#             sns.set_style("whitegrid")
#             sns.set_palette("deep")


class BokehThemer(Themer):
    """
    A class that manages themes for Bokeh.
    """

    pkg_name = "bokeh"

    def handle(self, theme: Theme) -> None:
        """
        Apply the theme to Bokeh.
        """
        from bokeh.io import curdoc  # type: ignore

        curdoc().theme = "dark_minimal" if theme == "dark" else "caliber"  # type: ignore


# class PygalThemer(Themer):
#     """
#     A class that manages themes for Pygal.
#     """

#     pkg_name = "pygal"

#     def handle(self, theme: Theme) -> None:
#         """
#         Apply the theme to Pygal.
#         """
#         import pygal

#         (
#             pygal.style.DarkStyle()
#             if theme == "dark"
#             else pygal.style.DefaultStyle()
#         )


# class PlotnineThemer(Themer):
#     """
#     A class that manages themes for Plotnine.
#     """

#     pkg_name = "plotnine"

#     def handle(self, theme: Theme) -> None:
#         """
#         Apply the theme to Plotnine.
#         """
#         from plotnine import theme_set, theme_dark, theme_light

#         theme_set(theme_dark() if theme == "dark" else theme_light())


class HoloviewsThemer(Themer):
    """
    A class that manages themes for Holoviews.
    """

    pkg_name = "holoviews"

    def handle(self, theme: Theme) -> None:
        """
        Apply the theme to Holoviews.
        """
        import holoviews as hv  # type: ignore

        hv.renderer("bokeh").theme = (
            "dark_minimal" if theme == "dark" else "caliber"
        )
        hv.renderer("plotly").theme = (
            "plotly_dark" if theme == "dark" else "plotly_white"
        )


# class YellowbrickThemer(Themer):
#     """
#     A class that manages themes for Yellowbrick.
#     """

#     pkg_name = "yellowbrick"

#     def handle(self, theme: Theme) -> None:
#         """
#         Apply the theme to Yellowbrick.
#         """
#         from yellowbrick.style import set_palette

#         set_palette('dark' if theme == "dark" else 'default')


# class NetworkxThemer(Themer):
#     """
#     A class that manages themes for Networkx.
#     """

#     pkg_name = "networkx"

#     def handle(self, theme: Theme) -> None:
#         """
#         Apply the theme to Networkx.
#         """
#         import networkx as nx

#         if theme == "dark":
#             nx.draw_default = lambda G, **kwargs: nx.draw(
#                 G, node_color='lightblue', edge_color='white', **kwargs
#             )
#         else:
#             nx.draw_default = nx.draw


def autohandle_third_party(theme: Theme) -> None:
    """
    Apply the theme to all third-party packages.
    """
    themers = [
        # MatplotlibThemer(),
        # SeabornThemer(),
        # PygalThemer(),
        # PlotnineThemer(),
        # YellowbrickThemer(),
        # NetworkxThemer(),
        AltairThemer(),
        PlotlyThemer(),
        BokehThemer(),
        HoloviewsThemer(),
    ]

    for themer in themers:
        try:
            if importlib.util.find_spec(themer.pkg_name) is not None:
                themer.handle(theme)
        except (ImportError, AttributeError) as e:
            LOGGER.debug(
                "Error applying %s theme to %s: %s",
                theme,
                themer.pkg_name,
                str(e),
            )
