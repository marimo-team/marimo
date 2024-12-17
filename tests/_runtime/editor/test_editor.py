import sys
import types

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


class TestCellRun:
    @staticmethod
    @pytest.mark.skipif(
        condition=not DependencyManager.pandas.has(),
        reason="requires matplotlib",
    )
    async def test_register_datasource(
        execution_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        registering_fn_module = types.ModuleType("registering_fn_module")
        exec(
            """
        import marimo as mo
        import pandas as pd

        def registering_fn() -> None:
            print('hi')
            df = pd.DataFrame({'a': [1], 'b': [2]})
            name_fn = lambda x: x
            mo.editor.register_datasource(df, name_fn('test_var_name'))
        """,
            registering_fn_module.__dict__,
        )

        # Add this module to `sys.modules`
        sys.modules["registering_fn_module"] = registering_fn_module
        k = execution_kernel
        await k.run(
            [
                exec_req.get(
                    """
                    import registering_fn_module
                    registering_fn_module.registering_fn()
                    """
                )
            ]
        )

        assert k.globals["registering_fn_module"]
        assert (
            "test_var_name" in k.globals
        ), "test_var_name not found in globals."
        import pandas as pd

        assert isinstance(
            k.globals["test_var_name"], pd.DataFrame
        ), "test_var_name is not a pandas DataFrame."
