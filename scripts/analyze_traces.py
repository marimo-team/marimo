import marimo

__generated_with = "0.8.0"
app = marimo.App(width="medium")


@app.cell
def __():
    import json

    import matplotlib.pyplot as plt
    import pandas as pd


    def parse_jsonl(file_path):
        traces = []
        with open(file_path, "r") as file:
            for line in file:
                traces.append(json.loads(line))
        return traces


    def create_dataframe(traces):
        df = pd.json_normalize(traces)
        df["duration"] = (
            df["end_time"] - df["start_time"]
        ) / 1e9  # Convert to seconds
        df["timestamp"] = pd.to_datetime(df["start_time"], unit="ns")

        # Extract HTTP method, path, and status code from attributes
        df["http_method"] = df["attributes"].apply(
            lambda x: x[0] if isinstance(x, list) and len(x) > 0 else None
        )
        df["http_path"] = df["attributes"].apply(
            lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None
        )
        df["http_status"] = df["attributes"].apply(
            lambda x: x[2] if isinstance(x, list) and len(x) > 2 else None
        )

        return df
    return create_dataframe, json, parse_jsonl, pd, plt


@app.cell
def __(parse_jsonl):
    import os

    file_path = "~/.marimo/traces/traces.jsonl"
    traces = parse_jsonl(os.path.expanduser(file_path))
    return file_path, os, traces


@app.cell
def __(create_dataframe, traces):
    df = create_dataframe(traces)
    return df,


@app.cell
def __(df):
    df
    return


@app.cell
def __(df):
    print(f"Total traces: {len(df)}")
    print(f"Average duration: {df['duration'].mean():.6f} seconds")
    return


@app.cell(hide_code=True)
def __(df):
    print("\nEndpoint distribution:")
    print(df["name"].value_counts())

    print("\nStatus code distribution:")
    print(df["http_status"].value_counts())

    print("\nTop 10 slowest requests:")
    slowest = df.nlargest(10, "duration")
    print(
        slowest[
            [
                "name",
                "duration",
                "context.trace_id",
                "http_method",
                "http_path",
                "http_status",
            ]
        ]
    )
    return slowest,


if __name__ == "__main__":
    app.run()
