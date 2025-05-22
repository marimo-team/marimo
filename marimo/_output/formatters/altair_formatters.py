# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import Literal

from marimo._config.config import Theme
from marimo._messaging.mimetypes import KnownMimeType, MimeBundleOrTuple
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.core.media import io_to_data_url
from marimo._plugins.ui._impl.altair_chart import (
    AltairChartType,
    maybe_make_full_width,
)
from marimo._plugins.ui._impl.charts.altair_transformer import (
    sanitize_nan_infs,
)


class AltairFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "altair"

    def register(self) -> None:
        import altair

        from marimo._output import formatting
        from marimo._plugins.ui._impl.charts.altair_transformer import (
            register_transformers,
        )

        # add marimo transformers
        register_transformers()

        @formatting.formatter(altair.TopLevelMixin)
        def _show_chart(chart: AltairChartType) -> tuple[KnownMimeType, str]:
            import altair as alt

            # Try to get the _repr_mimebundle_ method from the chart
            # If its HTML, we want to handle this ourselves
            # if its svg, vega, or png, then we want to pass that instead
            # because that means the user has configured the that renderer
            mimebundle: MimeBundleOrTuple = {}
            try:
                mimebundle = chart._repr_mimebundle_() or {}  # type: ignore
            except Exception:
                pass

            # Handle where there are multiple mime types
            # return as a mimebundle
            if len(mimebundle) > 1:
                return (
                    "application/vnd.marimo+mimebundle",
                    json.dumps(mimebundle),
                )

            # Handle non-HTML mime types
            non_html_mime_types: list[KnownMimeType] = [
                "image/svg+xml",
                "image/png",
                "application/vnd.vega.v5+json",
                "application/vnd.vegalite.v5+json",
            ]
            for mime_type in non_html_mime_types:
                if mime_type in mimebundle:
                    mime_response = mimebundle[mime_type]
                    if isinstance(mime_response, bytes):
                        data_url = io_to_data_url(mime_response, mime_type)
                        return (mime_type, data_url or "")
                    if isinstance(mime_response, str):
                        return mime_type, mime_response
                    return mime_type, json.dumps(mime_response)

            # If vegafusion is enabled, just wrap in altair_chart
            if alt.data_transformers.active.startswith("vegafusion"):
                return (
                    "application/vnd.vega.v5+json",
                    chart_to_json(chart=chart, spec_format="vega"),
                )

            # If the user has not set the max_rows option, we set it to 20_000
            # since we are able to handle the larger sizes (default is 5000)
            if "max_rows" not in alt.data_transformers.options:
                alt.data_transformers.options["max_rows"] = 20_000

            chart = _apply_embed_options(chart)

            chart = maybe_make_full_width(chart)

            # Return the chart as a vega-lite chart with embed options
            return (
                "application/vnd.vegalite.v5+json",
                chart_to_json(chart=chart, validate=False),
            )

    def apply_theme(self, theme: Theme) -> None:
        del theme
        # We don't need to apply this here because the theme is set in the
        # vega-lite component
        pass


# This is only needed since it seems that altair does not
# handle this internally.
# https://github.com/marimo-team/marimo/issues/2302
def _apply_embed_options(chart: AltairChartType) -> AltairChartType:
    import altair as alt

    # Respect user-set embed options
    # Note:
    # The python key is `embed_options`
    # The javascript key is `embedOptions`
    embed_options = alt.renderers.options.get("embed_options", {})
    prev_usermeta = {} if alt.Undefined is chart.usermeta else chart.usermeta
    chart["usermeta"] = {
        **prev_usermeta,
        "embedOptions": {
            **embed_options,
            **prev_usermeta.get("embedOptions", {}),
        },
    }
    return chart


def chart_to_json(
    chart: AltairChartType,
    spec_format: Literal["vega", "vega-lite"] = "vega-lite",
    validate: bool = True,
) -> str:
    """
    Convert an altair chart to a JSON string.

    This function is a wrapper around the altair.Chart.to_json method.
    It sanitizes the data in the chart if necessary and validates the spec.
    """
    try:
        return chart.to_json(
            format=spec_format,
            validate=validate,
            allow_nan=False,
            default=str,
        )
    except ValueError:
        chart.data = sanitize_nan_infs(chart.data)
        return chart.to_json(
            format=spec_format,
            validate=validate,
            allow_nan=False,
            default=str,
        )
