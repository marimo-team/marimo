# State

!!! warning "Stop! Read the interactivity guide first!"
    **Read the guide on [creating interactive
    elements](../guides/interactivity.md)** before reading this one!

!!! warning "Advanced topic!"
    This guide covers reactive state (`mo.state`), an advanced topic.

    **You likely don't need `mo.state`**. UI elements already have built-in
    state, their associated value, which you can access with their `value` attribute.
    For example, `mo.ui.slider()` has a value that is its current position on an
    interval, while `mo.ui.button()` has a value that can be configured to
    count the number of times it has been clicked, or to toggle between `True` and
    `False`. Additionally, interacting with UI elements bound to global variables
    [automatically executes cells](../guides/interactivity.md) that reference those
    variables, letting you react to changes by just reading their
    `value` attributes. **This functional paradigm is the preferred way of
    reacting to UI interactions in marimo.** **Chances are, the reactive
    execution built into UI elements will suffice.** (For example, [you don't need
    reactive state to handle a button click](../recipes.md#working-with-buttons).)

    That said, here are some signs you might need `mo.state`:

    - you need to maintain historical state related to a UI element that can't
      be computed from its built-in `value` (_e.g._, all values the user has
      ever input into a form)
    - you need to synchronize two different UI elements (_e.g._, so that
      interacting with either one controls the other)
    - you need to introduce cycles across cells

    **In over 99% of cases, you don't need and shouldn't use `mo.state`.** This
    feature can introduce hard-to-find bugs.

::: marimo.state
