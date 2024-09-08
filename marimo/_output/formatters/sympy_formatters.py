from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.ui._impl.anywidget.init import init_marimo_widget


from marimo._output.formatters.formatter_factory import FormatterFactory
#import marimo as mo

#print("LOADING SIMPY")
#from sympy import latex
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
        #print("Monkey-Patching", obj)
        # the lambda below is our sympy_html 
        obj._mime_ = lambda obj: ("text/html", mo.md(f"""\\[{latex(obj)}\\]""").text)
        #obj._mime_ = lambda obj: ("text/html", mo.md(f"""{latex(obj)}""").text)


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
        print("SYMPY FORMMATER REGISTARTION")
        import sympy  # type:ignore
        #from sympy import Symbol, Integral, Derivative, Pow, Matrix, Mul, Add, Piecewise
        from sympy.core.basic import Basic
        from sympy.core.basic import Printable

        #from sympy.physics.quantum.state import Wavefunction
        #monkey patching Symbol, Derivative, Pow etc
        #monkey patch the printable class so anything that can produce output with
        # latex(expr) e.g. latex(x**2) --> x^{2}
        patch_sympy(Printable)
        #patch_sympy(Symbol, Derivative, Pow, Matrix, Integral, Mul, 
        #            Add, Piecewise)


        #from sympy import symbols, Matrix, latex

        #from marimo._output import formatting
        # @formatting.formatter(Integral)
        #def _show_integral(integral: Integral) -> tuple[str, str]:
        #    return sympy_as_md(integral)

