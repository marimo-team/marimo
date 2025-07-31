# Setup references

You're probably on this page because you just saw an error like this one:

<div align="center">
<figure>
<img src="/_static/docs_setup_error.png" width="700px"/>
</figure>
</div>

marimo raises this error when the setup cell references variables defined in
other cells. In the example above, `image` is defined elsewhere in the notebook,
and hence cannot be referenced.

## Why can't I refer to variables?

The setup cell special: it runs before all other cells run, in order to provide
symbols that [top-level functions and classes](../reusing_functions.md) can use.
That's why it can't reference variables defined by other cells.

## How do I fix this error?

Define all needed variables in the setup cell. Or, if this code does not
need to run before all other cells (if you are not using top-level functions
or classes), simply move your code to a regular cell.
