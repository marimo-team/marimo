import marimo

__generated_with = "0.8.0"
app = marimo.App(width="medium")


@app.cell
def __():
    from opentelemetry import trace
    import altair as alt
    import json
    import marimo as mo
    import os
    import numpy as np

    import dataclasses
    import matplotlib.pyplot as plt
    import pandas as pd
    return alt, dataclasses, json, mo, np, os, pd, plt, trace


@app.cell(hide_code=True)
def __():
    from pydantic import BaseModel, Field, computed_field
    from typing import List, Dict, Optional, Any
    from datetime import datetime


    class Context(BaseModel):
        trace_id: str
        span_id: str
        trace_state: str


    class Status(BaseModel):
        status_code: str


    class ResourceAttributes(BaseModel):
        telemetry_sdk_language: str = Field(alias="telemetry.sdk.language")
        telemetry_sdk_name: str = Field(alias="telemetry.sdk.name")
        telemetry_sdk_version: str = Field(alias="telemetry.sdk.version")
        service_name: str = Field(alias="service.name")


    class Resource(BaseModel):
        attributes: ResourceAttributes
        schema_url: str


    class Span(BaseModel):
        name: str
        context: Context
        kind: str
        parent_id: Optional[str]
        start_time: datetime
        end_time: datetime
        status: Status
        attributes: Dict[str, Any]
        events: List = []
        links: List = []
        resource: Resource
        relative_start: Optional[datetime] = None
        depth: Optional[int] = 0

        @computed_field
        @property
        def duration_ms(self) -> float:
            return (self.end_time - self.start_time).microseconds / 1000

        @classmethod
        def parse(cls, data: Dict) -> "Span":
            # Convert string timestamps to datetime objects
            data["start_time"] = datetime.fromisoformat(
                data["start_time"].rstrip("Z")
            )
            data["end_time"] = datetime.fromisoformat(data["end_time"].rstrip("Z"))

            # Parse the nested Resource structure
            resource_data = data["resource"]
            resource_data["attributes"] = ResourceAttributes(
                **resource_data["attributes"]
            )
            data["resource"] = Resource(**resource_data)

            # Handle the trace_state as a string
            if isinstance(data["context"]["trace_state"], list):
                data["context"]["trace_state"] = str(
                    data["context"]["trace_state"]
                )

            return cls(**data)
    return (
        Any,
        BaseModel,
        Context,
        Dict,
        Field,
        List,
        Optional,
        Resource,
        ResourceAttributes,
        Span,
        Status,
        computed_field,
        datetime,
    )


@app.cell
def __(Dict, List, Span, json):
    def parse_jsonl(file_path):
        spans = []
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                spans.append(Span.parse(json.loads(line)))
        return spans


    def populate_depth(spans: List[Span]) -> List[Span]:
        # Sort spans by start_time
        sorted_spans = sorted(spans, key=lambda span: span.start_time)

        # Create a dictionary to store spans by their ID
        span_dict: Dict[str, Span] = {
            span.context.span_id: span for span in sorted_spans
        }

        # Function to recursively calculate depth
        def calculate_depth(span: Span, current_depth: int = 0) -> int:
            if span.depth is not None:
                return span.depth

            span.depth = current_depth

            # If this span has a parent, calculate the parent's depth first
            if span.parent_id and span.parent_id in span_dict:
                parent_span = span_dict[span.parent_id]
                parent_depth = calculate_depth(parent_span, current_depth)
                span.depth = parent_depth + 1

            return span.depth

        # Calculate depth for all spans
        for span in sorted_spans:
            calculate_depth(span)
        return sorted_spans
    return parse_jsonl, populate_depth


@app.cell
def __(mo):
    refresh = mo.ui.refresh(options=[2, 5, 10], default_interval=5)
    refresh
    return refresh,


@app.cell
def __(os, parse_jsonl, populate_depth, refresh):
    refresh
    file_path = "~/.marimo/traces/spans.jsonl"
    spans = parse_jsonl(os.path.expanduser(file_path))
    spans = populate_depth(spans)
    len(spans)
    return file_path, spans


@app.cell
def __(spans):
    json_spans = [trace.model_dump(mode="serialization") for trace in spans]
    return json_spans,


@app.cell
def __(json_spans, mo):
    mo.ui.table(json_spans)
    return


@app.cell
def __(Span, pd):
    def spans_to_dataframe(spans: Span):
        data = []
        for span in spans:
            row = {
                "name": span.name,
                "kind": span.kind,
                "parent_id": span.parent_id,
                "start_time": span.start_time,
                "end_time": span.end_time,
                "status": span.status.status_code,
                "duration_ms": span.duration_ms,
                "depth": span.depth,
                "service_name": span.resource.attributes.service_name,
            }
            data.append(row)

        return pd.DataFrame(data)
    return spans_to_dataframe,


@app.cell
def __(spans, spans_to_dataframe):
    df = spans_to_dataframe(spans)
    df
    return df,


@app.cell
def __(df):
    df[["name", "duration_ms"]]
    return


@app.cell(hide_code=True)
def __(spans):
    total_duration = (
        max(span.end_time for span in spans)
        - min(span.start_time for span in spans)
    ).total_seconds() * 1000
    total_duration
    return total_duration,


@app.cell
def __(alt, df):
    duration_chart = (
        alt.Chart(df)
        .mark_bar()
        .interactive()
        .encode(
            x=alt.X("duration_ms:Q", bin=True, title="Duration (ms)"),
            y="count()",
            color="service_name:N",
        )
        .properties(
            title="Span Duration Distribution by Service", width=600, height=400
        )
    )

    duration_chart = (
        alt.Chart(df)
        .mark_bar()
        .interactive()
        .encode(
            x=alt.X("duration_ms:Q", bin=True, title="Duration (ms)"),
            y="count()",
            color="service_name:N",
        )
        .properties(
            title="Span Duration Distribution by Service", width=600, height=400
        )
    )

    service_count_chart = (
        alt.Chart(df)
        .mark_bar()
        .interactive()
        .encode(x="service_name:N", y="count()", color="service_name:N")
        .properties(title="Span Count by Service", width=600, height=400)
    )

    timeline_chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("start_time:T", title="Time"),
            x2="end_time:T",
            y="name:N",
            color="service_name:N",
            tooltip=["name", "duration_ms", "service_name"],
        )
        .properties(title="Span Timeline", width=800, height=400)
    )

    status_chart = (
        alt.Chart(df)
        .mark_bar()
        .interactive()
        .encode(x="status:N", y="count()", color="status:N")
        .properties(title="Span Status Distribution", width=400, height=300)
    )

    depth_chart = (
        alt.Chart(df)
        .mark_bar()
        .interactive()
        .encode(x="depth:O", y="count()", color="depth:O")
        .properties(title="Span Depth Distribution", width=400, height=300)
    )
    return (
        depth_chart,
        duration_chart,
        service_count_chart,
        status_chart,
        timeline_chart,
    )


@app.cell
def __(duration_chart):
    duration_chart
    return


@app.cell
def __(timeline_chart):
    timeline_chart
    return


@app.cell
def __(depth_chart, status_chart):
    status_chart | depth_chart
    return


if __name__ == "__main__":
    app.run()
