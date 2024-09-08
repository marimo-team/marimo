from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.ui._impl.anywidget.init import init_marimo_widget


from marimo._output.formatters.formatter_factory import FormatterFactory

def patch_sympy(*objs):
    import marimo as mo
    """adds the _mime_() method to the sympy objects
    e.g.
    Symbol._mime_ = sympy_html
    example:
    patch_sympy(Symbol, Integral)
    """
    from sympy import latex
    for obj in objs:
        # the lambda below is our sympy_html 
        obj._mime_ = lambda obj: ("text/html", mo.md(f"""\\[{latex(obj)}\\]""").text)


def sympy_as_md(obj):
    import marimo as mo
    from sympy import latex
    """adds the _mime_() method to the sympy objects
    e.g.
    Symbol._mime_ = sympy_html
    example:
    patch_sympy(Symbol, Integral)
    """
    return ("text/html", mo.md(f"""\\[{latex(obj)}\\]""").text)


class SympyFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "sympy"

    def register(self) -> None:
        import sympy  # type:ignore
        from sympy.core.basic import Printable

        # We will monkey-patch the Printable class so most Sympy constructs
        # that can be "pretty-printed" that with sympy.latex
        # can also be rendered in marimo.
        # One way to test if an experssion is supported is
        # with latex(expr) 
        # e.g. latex(x**2) --> x^{2}
        patch_sympy(Printable)

        #from marimo._output import formatting
        # @formatting.formatter(Integral)
        #def _show_integral(integral: Integral) -> tuple[str, str]:
        #    return sympy_as_md(integral)

