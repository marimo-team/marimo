import marimo

__generated_with = "0.9.34"
app = marimo.App(width="full", auto_download=["html"])


@app.cell
def __(alt, df, mo):
    tmc = mo.ui.altair_chart(
        alt.Chart(df.reset_index())
        .mark_bar()
        .encode(
            x="count()",
            y="timestamp",
        )
    )
    tmc
    return (tmc,)


@app.cell
def __(tmc):
    tmc.value
    return


@app.cell
def __(build_df, d):
    df = build_df(d)
    return (df,)


@app.cell
def __(StringIO, date_format, pd):
    def build_df(data: str):
        res = pd.read_csv(StringIO(data))
        res["timestamp"] = pd.to_datetime(
            res["@timestamp"], format=date_format
        ).dt.floor("s")
        res.index = res["timestamp"]
        res = res.rename(columns={"kubernetes.pod_name": "server"})

        res = res[
            [
                "message",
                "server",
            ]
        ]

        return res

    return (build_df,)


@app.cell
def __():
    date_format = "%b %d, %Y @ %H:%M:%S.%f"
    return (date_format,)


@app.cell
def __():
    d = '''"@timestamp",message,severity,"kubernetes.pod_name"
    "Nov 26, 2024 @ 00:29:59.795","time=""2024-11-26T00:29:59Z"" level=info msg=""app_disconn(device-ap-c8a608174aa0)(ap)(209766850)(1)(1)(Client Closed)(thirdparty-nats-3)"" @service=benthos label="""" path=root.pipeline.processors.0.workflow.processors.1 stream=sys_evts_acct_conn_disconn",,"thirdparty-benthos-fbfb4884d-wf775"
    "Nov 26, 2024 @ 00:29:59.794","time=""2024-11-26T00:29:59Z"" level=info msg=""app_conn(device-ap-58fb961a30d0)(ap)(thirdparty-nats-4)"" @service=benthos label="""" path=root.pipeline.processors.0.workflow.processors.1 stream=sys_evts_acct_conn_disconn",,"thirdparty-benthos-fbfb4884d-wf775"
    "Nov 26, 2024 @ 00:29:59.793","time=""2024-11-26T00:29:58Z"" level=info msg=""app_conn(device-ap-a80bfb3d7f80)(ap)(thirdparty-nats-4)"" @service=benthos label="""" path=root.pipeline.processors.0.workflow.processors.1 stream=sys_evts_acct_conn_disconn",,"thirdparty-benthos-fbfb4884d-wf775"
    "Nov 26, 2024 @ 00:29:59.791","time=""2024-11-26T00:29:58Z"" level=info msg=""app_disconn(device-ap-58fb961a4220)(ap)(177150315)(0)(0)(Client Closed)(thirdparty-nats-2)"" @service=benthos label="""" path=root.pipeline.processors.0.workflow.processors.1 stream=sys_evts_acct_conn_disconn",,"thirdparty-benthos-fbfb4884d-wf775"
    "Nov 26, 2024 @ 00:29:58.012","time=""2024-11-26T00:29:56Z"" level=info msg=""app_conn(device-ap-cc1b5a3008c0)(ap)(thirdparty-nats-1)"" @service=benthos label="""" path=root.pipeline.processors.0.workflow.processors.1 stream=sys_evts_acct_conn_disconn",,"thirdparty-benthos-fbfb4884d-rzlc5"
    "Nov 26, 2024 @ 00:29:58.011","time=""2024-11-26T00:29:56Z"" level=info msg=""app_conn(device-ap-a80bfb3d79d0)(ap)(thirdparty-nats-3)"" @service=benthos label="""" path=root.pipeline.processors.0.workflow.processors.1 stream=sys_evts_acct_conn_disconn",,"thirdparty-benthos-fbfb4884d-rzlc5"
    "Nov 26, 2024 @ 00:29:58.010","time=""2024-11-26T00:29:55Z"" level=info msg=""app_disconn(device-ap-d04f58243120)(ap)(87695134)(1)(1)(Client Closed)(thirdparty-nats-0)"" @service=benthos label="""" path=root.pipeline.processors.0.workflow.processors.1 stream=sys_evts_acct_conn_disconn",,"thirdparty-benthos-fbfb4884d-rzlc5"
    "Nov 26, 2024 @ 00:29:58.009","time=""2024-11-26T00:29:55Z"" level=info msg=""app_disconn(device-ap-38453b263ef0)(ap)(37625737)(2)(1)(Client Closed)(thirdparty-nats-1)"" @service=benthos label="""" path=root.pipeline.processors.0.workflow.processors.1 stream=sys_evts_acct_conn_disconn",,"thirdparty-benthos-fbfb4884d-rzlc5"
    "Nov 26, 2024 @ 00:29:58.008","time=""2024-11-26T00:29:53Z"" level=info msg=""app_disconn(device-ap-c8a6081727b0)(ap)(105295015)(1)(1)(Client Closed)(thirdparty-nats-3)"" @service=benthos label="""" path=root.pipeline.processors.0.workflow.processors.1 stream=sys_evts_acct_conn_disconn",,"thirdparty-benthos-fbfb4884d-rzlc5"
    '''
    return (d,)


@app.cell
def __():
    from io import StringIO

    import altair as alt
    import numpy as np
    import pandas as pd

    import marimo as mo

    return StringIO, alt, mo, np, pd


if __name__ == "__main__":
    app.run()
