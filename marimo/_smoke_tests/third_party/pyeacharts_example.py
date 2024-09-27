import marimo

__generated_with = "0.8.18"
app = marimo.App(width="medium")


@app.cell
def __():
    import pyecharts.options as opts
    from pyecharts.charts import Bar

    bar = (
        Bar()
        .add_xaxis(["shirt", "cardigan", "chiffon", "pants", "heels", "socks"])
        .add_yaxis("Merchant A", [5, 20, 36, 10, 75, 90])
        .add_yaxis("Merchant B", [15, 6, 45, 20, 35, 66])
        .set_global_opts(
            title_opts=opts.TitleOpts(title="Main Title", subtitle="Subtitle")
        )
    )

    bar
    return Bar, bar, opts


if __name__ == "__main__":
    app.run()
