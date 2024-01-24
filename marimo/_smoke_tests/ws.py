# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.39"
app = marimo.App(width="full")


@app.cell
def __(mo, os):
    env_api_key = os.environ.get("COINBASE_API_KEY")
    env_api_secret = os.environ.get("COINBASE_API_SECRET")

    api_key_input = mo.ui.text(value=env_api_key or "", label="YOUR_API_KEY")
    api_secret_input = mo.ui.text(
        value=env_api_secret or "",
        label="YOUR_API_SECRET",
        kind="password",
    )


    mo.accordion(
        {
            "💻 Configuration": mo.vstack(
                [
                    api_key_input,
                    api_secret_input,
                ]
            )
        }
    )
    return api_key_input, api_secret_input, env_api_key, env_api_secret


@app.cell
def __(mo, pd):
    get_df, set_df = mo.state(
        pd.DataFrame(
            columns=[
                "timestamp",
                "type",
                "product_id",
                "price",
                "volume_24_h",
                "low_24_h",
                "high_24_h",
                "low_52_w",
                "high_52_w",
                "price_percent_chg_24_h",
            ]
        )
    )
    return get_df, set_df


@app.cell
def __(mo):
    def output_stats(df):
        if len(df) == 0:
            return mo.callout("Waiting for data...")

        lastupdate = df["timestamp"].iloc[-1]

        high24 = df["high_24_h"].iloc[-1]
        low24 = df["low_24_h"].iloc[-1]
        diff_high24_to_now = float(high24) - float(df["price"].iloc[-1])
        diff_high24_to_now_percent = (
            diff_high24_to_now / float(df["price"].iloc[-1]) * 100
        )
        diff_low24_to_now = float(low24) - float(df["price"].iloc[-1])
        diff_low24_to_now_percent = (
            diff_low24_to_now / float(df["price"].iloc[-1]) * 100
        )

        return mo.hstack(
            [
                mo.stat(
                    label="Ticker",
                    value=df["product_id"].iloc[-1],
                    caption=f"Last updated: {lastupdate}",
                    bordered=True,
                ),
                mo.stat(
                    label="Price",
                    value=df["price"].iloc[-1],
                    caption=f"24h change: {df['price_percent_chg_24_h'].iloc[-1]:.05}%",
                    bordered=True,
                    direction="increase"
                    if float(df["price_percent_chg_24_h"].iloc[-1]) > 0
                    else "decrease",
                ),
                mo.stat(
                    label="Volume",
                    value=df["volume_24_h"].iloc[-1],
                    caption="In the past 24 hours",
                    bordered=True,
                ),
                mo.stat(
                    label="24h high",
                    value=high24,
                    caption=f"Diff: {diff_high24_to_now:.2f} ({diff_high24_to_now_percent:.2f}%)",
                    bordered=True,
                ),
                mo.stat(
                    label="24h low",
                    value=low24,
                    caption=f"Diff: {diff_low24_to_now:.2f} ({diff_low24_to_now_percent:.2f}%)",
                    bordered=True,
                ),
            ],
            justify="space-between",
            widths=[1, 1, 1, 1, 1, 1],
            gap=2,
        )
    return output_stats,


@app.cell
def __(alt, mo):
    def output_chart(df):
        _chart = (
            alt.Chart(df)
            .mark_line()
            .encode(
                x="timestamp:T",
                y=alt.Y("price:Q").scale(zero=False),
                color="product_id:N",
                tooltip=["timestamp:T", "price:Q", "product_id:N"],
            )
        )
        return mo.ui.altair_chart(_chart)
    return output_chart,


@app.cell
def __(mo):
    def output_table(df):
        return mo.ui.table(df[::-1], selection=None)
    return output_table,


@app.cell
def __(
    WebSocketConnectionClosedException,
    api_key_input,
    api_secret_input,
    create_connection,
    e,
    get_df,
    hashlib,
    hmac,
    json,
    mo,
    output_chart,
    output_stats,
    output_table,
    set_df,
    time,
):
    mo.stop(
        not api_key_input.value or not api_secret_input.value,
        mo.md(
            f"""
            API key and secret required. 

            You can create one from Coinbase following [these instructions](https://help.coinbase.com/en/exchange/managing-my-account/how-to-create-an-api-key).
            """
        ).callout(),
    )

    ws = None
    thread = None
    thread_running = False
    thread_keepalive = None


    def add_signature_ws(message: dict, secret: str):
        nonce = int(time.time())
        to_sign = f"{nonce}{message['channel']}{','.join(message['product_ids'])}"
        signature = hmac.new(
            secret.encode("utf-8"), to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        message["signature"] = signature
        message["timestamp"] = str(nonce)
        return message


    def handle_new_ticker(data):
        print(data)
        if data["channel"] == "ticker":
            datum = data["events"][0]["tickers"][0]
            current = get_df()
            current.loc[len(current)] = [
                data["timestamp"],
                datum["type"],
                datum["product_id"],
                datum["price"],
                datum["volume_24_h"],
                datum["low_24_h"],
                datum["high_24_h"],
                datum["low_52_w"],
                datum["high_52_w"],
                datum["price_percent_chg_24_h"],
            ]
            set_df(current)
            mo.output.replace(
                mo.vstack(
                    [
                        mo.md(
                            f"""
                        Since marimo does not let other cells runt until the current cell has completed,
                        we must output the UI in the same cell as the websocket thread.

                        This cell runs a websocket indefinitely, until manually interrupted.

                        Ideally we can run this cell async, not blocking other cells, or run in a thread
                        and have the data be updated in the UI.
                        """
                        ),
                        output_stats(current),
                        output_chart(current),
                        output_table(current),
                    ]
                )
            )


    def websocket_thread():
        api_key = api_key_input.value
        api_secret = api_secret_input.value

        ticker_batch = {
            "type": "subscribe",
            "product_ids": ["ETH-USD"],
            "channel": "ticker",
            "api_key": api_key,
        }

        ws = create_connection("wss://advanced-trade-ws.coinbase.com")
        msg = add_signature_ws(ticker_batch, api_secret)
        ws.send(json.dumps(msg))

        # thread_keepalive.start()
        while not thread_running:
            try:
                data = ws.recv()
                if data != "":
                    msg = json.loads(data)
                else:
                    msg = {}
            except ValueError as e:
                print(e)
                print("{} - data: {}".format(e, data))
            except Exception as e:
                print(e)
                print("{} - data: {}".format(e, data))
            else:
                if "result" not in msg:
                    handle_new_ticker(msg)

        try:
            if ws:
                ws.close()
        except WebSocketConnectionClosedException:
            pass
        finally:
            thread_keepalive.join()


    def websocket_keepalive(interval=30):
        while ws.connected:
            ws.ping("keepalive")
            time.sleep(interval)


    # thread = Thread(target=websocket_thread)
    # thread_keepalive = Thread(target=websocket_keepalive)
    # thread.start()
    websocket_thread()
    return (
        add_signature_ws,
        handle_new_ticker,
        thread,
        thread_keepalive,
        thread_running,
        websocket_keepalive,
        websocket_thread,
        ws,
    )


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    import altair as alt
    import os
    return alt, mo, os, pd


@app.cell
def __():
    import json
    import time
    import hmac
    import hashlib
    from threading import Thread
    from websocket import create_connection, WebSocketConnectionClosedException
    return (
        Thread,
        WebSocketConnectionClosedException,
        create_connection,
        hashlib,
        hmac,
        json,
        time,
    )


if __name__ == "__main__":
    app.run()
