# NB! The only difference between this file and transitive_wrappers_1.py is that
# impure_state is tweaked.
import marimo

__generated_with = "0.14.12"
app = marimo.App()

with app.setup:
    import functools
    from typing import Any

    import marimo as mo

    # This will be an impure decorator (contains non-primitive objects)
    # impure_state = [object()] in transitive_wrappers_1.py
    impure_state = [object(), object()]


@app.function
def my_impure_decorator(func):
    """An impure decorator that depends on impure_state"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        # Decorator depends on impure_state
        wrapper._call_count = len(impure_state)
        return func(*args, **kwargs)

    return wrapper


@app.function
def my_pure_decorator(func):
    """Same pure decorator"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        return func(*args, **kwargs)

    return wrapper


@app.function
@my_impure_decorator
def pure_function():
    # This function itself is pure (no external dependencies)
    return 42


@app.function
@my_pure_decorator
def impure_function():
    # Same function, but now depends on different impure_dependency
    return len(impure_state)


@app.function
@mo.cache
def impure_wrapped_pure():
    return pure_function()


@app.function
@mo.cache
def pure_wrapped_impure():
    return impure_function()


if __name__ == "__main__":
    app.run()
