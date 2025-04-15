import marimo

__generated_with = "0.12.9-dev12"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    slider = mo.ui.slider(1, 100)

    class has_mime:
      @staticmethod
      def _mime_():
          # post_execution_hook reuses the name cell index space
          # as the general cell
          # The temp value overwrites the one on the generally cell
          # And because the temp value is "finalized"
          # The cell reference is deleted
          return slider._clone()._mime_()

    has_mime()
    return has_mime, mo, slider


@app.cell
def _(slider):
    slider.value
    return


if __name__ == "__main__":
    app.run()
