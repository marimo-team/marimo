# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import Any, Literal
from urllib.request import urlopen

from marimo._config.config import Theme
from marimo._dependencies.dependencies import DependencyManager
from marimo._loggers import marimo_logger
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

LOGGER = marimo_logger()


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

    # If embed_options is None or empty, return chart with empty embedOptions
    # if not embed_options:
    #     chart["usermeta"] = {
    #         **prev_usermeta,
    #         "embedOptions": {},
    #     }
    #     return chart

    embed_options = _apply_format_locales(embed_options)

    chart["usermeta"] = {
        **prev_usermeta,
        "embedOptions": {
            **embed_options,
            **prev_usermeta.get("embedOptions", {}),
        },
    }
    return chart


FETCH_TIMEOUT = 3
TIME_FORMAT_LOCALE_URL = (
    "https://unpkg.com/d3-time-format@latest/locale/{locale}.json"
)
FORMAT_LOCALE_URL = "https://unpkg.com/d3-format@latest/locale/{locale}.json"


def _apply_format_locales(embed_options: dict[str, Any]) -> dict[str, Any]:
    """Apply format localizations to embed options using either vl_convert or d3 format files."""

    def get_time_format_locale(locale: str) -> dict[str, Any]:
        try:
            if DependencyManager.vl_convert_python.has():
                import vl_convert as vlc  # type: ignore

                return dict(vlc.get_time_format_locale(locale))
            else:
                with urlopen(
                    TIME_FORMAT_LOCALE_URL.format(locale=locale),
                    timeout=FETCH_TIMEOUT,
                ) as response:
                    return dict(json.loads(response.read()))
        except Exception as e:
            LOGGER.warning(f"Error getting time format locale: {e}")
            return {}

    def get_format_locale(locale: str) -> dict[str, Any]:
        try:
            if DependencyManager.vl_convert_python.has():
                import vl_convert as vlc  # type: ignore

                return dict(vlc.get_format_locale(locale))
            else:
                with urlopen(
                    FORMAT_LOCALE_URL.format(locale=locale),
                    timeout=FETCH_TIMEOUT,
                ) as response:
                    return dict(json.loads(response.read()))
        except Exception as e:
            LOGGER.warning(f"Error getting format locale: {e}")
            return {}

    if "timeFormatLocale" in embed_options:
        time_format_locale = embed_options["timeFormatLocale"]
        if isinstance(time_format_locale, str):
            embed_options["timeFormatLocale"] = get_time_format_locale(
                time_format_locale
            )

    if "formatLocale" in embed_options:
        format_locale = embed_options["formatLocale"]
        if isinstance(format_locale, str):
            embed_options["formatLocale"] = get_format_locale(format_locale)

    return embed_options


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
