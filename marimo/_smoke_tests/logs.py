# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.13.11"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    level_dropdown = mo.ui.dropdown(
        label="Log level",
        options=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        value="INFO",
    )
    level_dropdown
    return (level_dropdown,)


@app.cell
def _(level_dropdown):
    # Configure logging
    import logging

    logger = logging.getLogger(__name__)
    logger.setLevel(level_dropdown.value)

    # Test different log levels
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    logger.critical("This is a CRITICAL message")
    return logger, logging


@app.cell
def _(logger, mo):
    # Test logging in a cell with output
    logger.info("Starting computation...")
    result = 42
    logger.debug(f"Result computed: {result}")
    mo.md(f"The result is {result}")
    return


@app.cell
def _(logger):
    # Test logging with exception
    try:
        x = 1 / 0
    except ZeroDivisionError as e:
        logger.error("Division by zero!", exc_info=True)
    return


@app.cell
def _(level_dropdown, logging):
    # Test logging with custom formatting
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    _logger = logging.getLogger("custom_logger")
    _logger.addHandler(handler)
    _logger.setLevel(level_dropdown.value)
    _logger.info("Custom formatted log message")

    # Test logging with extra context
    extra_logger = logging.getLogger("context_logger")
    extra = {"user": "john", "ip": "192.168.1.1"}
    extra_logger.info("User action", extra=extra)

    # Test logging with different string formatting
    template_logger = logging.getLogger("template_logger")
    name = "Alice"
    age = 30
    template_logger.info("User %s is %d years old", name, age)
    template_logger.info(f"User {name} is {age} years old")
    template_logger.info(
        "User %(name)s is %(age)d years old", {"name": name, "age": age}
    )
    return


if __name__ == "__main__":
    app.run()
