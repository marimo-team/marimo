# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "anywidget==0.9.21",
#     "marimo>=0.20.2",
#     "traitlets==5.14.3",
# ]
# ///
import marimo

__generated_with = "unknown"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(CounterWidget):
    CounterWidget(count=42)
    return


@app.cell
def _(anywidget, os, traitlets):
    class CounterWidget(anywidget.AnyWidget):
        _esm = """
        export default async () => {
          let hostName = null;

          return {
            initialize({ model }) {
              // This message gets handled by _handle_custom_msg on the Python side
              model.send({ event: "requestHostName" });
            },

            render({ model, el }) {
              let count = () => model.get("count");
              let btn = document.createElement("button");
              btn.classList.add("counter-button");
              btn.innerHTML = `Initializing...`;

              // Set proper HTML content once message arrives from Python connection
              model.on("msg:custom", (msg, buffers) => {
                hostName = msg.response;
                btn.innerHTML = `count is ${count()} from ${hostName} host`;
              });

              btn.addEventListener("click", () => {
                model.set("count", count() + 1);
                model.save_changes();
              });

              model.on("change:count", () => {
                btn.innerHTML =
                  hostName
                    ? `count is ${count()} from ${hostName} host`
                    : `Initializing...`;
              });

              el.appendChild(btn);
            },
          };
        };
        """
        _css = """
        .counter-button {
          background: #387262;
          border: 0;
          border-radius: 10px;
          padding: 10px 50px;
          color: white;
        }
        """
        count = traitlets.Int(0).tag(sync=True)

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.on_msg(self._handle_custom_msg)

        def _handle_custom_msg(self, *args, **kwargs):
            self.send({"response": os.name})

    return (CounterWidget,)


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import anywidget
    import traitlets
    import os

    return anywidget, os, traitlets


if __name__ == "__main__":
    app.run()
