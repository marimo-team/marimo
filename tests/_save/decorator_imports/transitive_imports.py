import marimo

__generated_with = "0.14.15"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo
    import math
    import tests._save.decorator_imports.module_1 as my_module



@app.function
@mo.cache
def has_import():
    return len([mo])


@app.function
@mo.cache
def doesnt_have_import():
    return len([mo, math])


@app.function
@mo.cache(pin_modules=True)
def doesnt_have_namespace_pinned() -> None:
    return my_module.__version__

@app.function
@mo.cache
def doesnt_have_namespace() -> None:
    return my_module.__version__


if __name__ == "__main__":
    app.run()
