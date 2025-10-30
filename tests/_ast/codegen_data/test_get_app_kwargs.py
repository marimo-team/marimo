import marimo

__generated_with = "0.17.4"
app = marimo.App(
    app_title="title",
    auto_download="html",
    layout_file="layouts/layout.json",
    invalid_arg=1
)


if __name__ == "__main__":
    app.run()
