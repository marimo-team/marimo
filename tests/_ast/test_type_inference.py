# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import importlib.util
from typing import TYPE_CHECKING

import pytest

from marimo._ast import codegen
from marimo._ast.cell import CellConfig
from marimo._ast.codegen import pop_setup_cell
from marimo._ast.names import SETUP_CELL_NAME
from marimo._ast.toplevel import TopLevelExtraction
from marimo._ast.type_inference import (
    Inferred,
    JediBackend,
    candidate_names,
    definition_sites,
    infer_annotations,
    lower_hint,
    module_aliases,
    probe_module,
    to_annotation,
)

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._ast.cell import CellImpl

BUILTIN_REFS = {"int", "str", "bool", "bytes", "list", "dict", "tuple", "set"}


def make_extraction(
    codes: list[str], setup: str | None = None
) -> tuple[TopLevelExtraction, CellImpl | None]:
    names = ["_" for _ in codes]
    configs = [CellConfig() for _ in codes]
    if setup is not None:
        codes = [setup, *codes]
        names = [SETUP_CELL_NAME, *names]
        configs = [CellConfig(), *configs]
    setup_cell = pop_setup_cell(codes, names, configs)
    toplevel_defs = set(setup_cell.defs) if setup_cell else set()
    return TopLevelExtraction(codes, names, configs, toplevel_defs), setup_cell


def instance(full_name: str, hint: str | None = None) -> Inferred:
    return Inferred(full_name, "instance", hint)


class FakeBackend:
    """Answers with canned inferences and resolves canned class spellings.

    `classes` maps an expression such as `pd.DataFrame` to the class it
    names. Any other expression resolves to nothing.
    """

    def __init__(
        self,
        inferred: dict[str, list[Inferred]],
        classes: dict[str, str] | None = None,
    ) -> None:
        self.inferred = inferred
        self.classes = classes or {}
        self.sources: list[str] = []
        self.resolved: list[str] = []
        self.search_paths: list[Path | None] = []

    def infer_definitions(
        self, source: str, names: set[str], search_path: Path | None
    ) -> dict[str, list[Inferred]]:
        self.sources.append(source)
        self.search_paths.append(search_path)
        return {n: v for n, v in self.inferred.items() if n in names}

    def resolve(
        self, source: str, expressions: list[str], search_path: Path | None
    ) -> list[Inferred | None]:
        del source, search_path
        self.resolved.extend(expressions)
        return [
            Inferred(self.classes[e], "class") if e in self.classes else None
            for e in expressions
        ]


def generate(
    codes: list[str],
    setup: str | None = None,
    *,
    backend: FakeBackend | None = None,
    infer_types: str = "jedi",
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> str:
    names = ["_" for _ in codes]
    configs = [CellConfig() for _ in codes]
    if setup is not None:
        codes = [setup, *codes]
        names = [SETUP_CELL_NAME, *names]
        configs = [CellConfig(), *configs]
    if backend is not None:
        assert monkeypatch is not None
        monkeypatch.setattr(
            "marimo._ast.type_inference.JediBackend", lambda: backend
        )
    return codegen.generate_filecontents(
        codes,
        names,
        configs,
        infer_types=infer_types,  # type: ignore[arg-type]
    )


class TestCandidateNames:
    def test_only_public_unannotated_names_read_by_other_cells(self) -> None:
        extraction, _ = make_extraction(
            [
                "x = 1",
                "y: int = 2",
                "unused = 3",
                "_private = 4",
                "print(x, y, K, _private)",
            ],
            setup="K = 1",
        )
        # `y` is annotated, `unused` is never read, `_private` is local to
        # its cell, and `K` is module scope in the generated file.
        assert candidate_names(extraction) == {"x"}

    def test_sql_definitions_are_skipped(self) -> None:
        extraction, _ = make_extraction(
            [
                'mo.sql("CREATE TABLE t AS SELECT 1 AS a")',
                'df = mo.sql("SELECT * FROM t")',
                "print(df)",
            ],
        )
        # The second cell reads `t`, so only the SQL rule keeps it out.
        assert "t" in extraction.used_refs
        names = candidate_names(extraction)
        assert "t" not in names
        assert "df" in names


class TestModuleAliases:
    def test_only_module_bindings(self) -> None:
        _, setup_cell = make_extraction(
            ["print(np, pd, Path, math)"],
            setup=(
                "import numpy as np\n"
                "import pandas as pd\n"
                "from pathlib import Path\n"
                "import math"
            ),
        )
        assert module_aliases(setup_cell) == {
            "math": "math",
            "np": "numpy",
            "pd": "pandas",
        }

    def test_no_setup_cell(self) -> None:
        assert module_aliases(None) == {}


class TestProbeModule:
    def test_definitions_precede_uses(self) -> None:
        extraction, setup_cell = make_extraction(
            ["y = x + 1", "x = 1", "print(x, y)"],
            setup="import math",
        )
        lines = probe_module(extraction, setup_cell).splitlines()
        assert lines[0] == "import math"
        assert lines.index("x = 1") < lines.index("y = x + 1")

    def test_cycles_fall_back_to_file_order(self) -> None:
        extraction, _ = make_extraction(["a = b", "b = a", "print(a, b)"])
        lines = probe_module(extraction, None).splitlines()
        assert lines[:3] == ["a = b", "b = a", "print(a, b)"]


class TestDefinitionSites:
    def test_module_level_bindings_of_every_kind(self) -> None:
        source = (
            "x = 1\n"
            "if x:\n"
            "    x = 2\n"
            "for item in [1]:\n"
            "    pass\n"
            "with open('f') as handle:\n"
            "    pass\n"
            "first, second = 1, 2\n"
            "print(walrus := 3)\n"
            "def f():\n"
            "    x = 'not module level'\n"
            "squares = [x for x in range(3)]\n"
        )
        names = {"x", "item", "handle", "first", "second", "walrus", "squares"}
        sites = definition_sites(source, names)
        assert sites["x"] == [(1, 0), (3, 4)]
        assert sites["item"] == [(4, 4)]
        assert sites["handle"] == [(6, 18)]
        assert sites["first"] == [(8, 0)]
        assert sites["second"] == [(8, 7)]
        assert sites["walrus"] == [(9, 6)]
        # The comprehension variable is not a module-level `x`.
        assert sites["squares"] == [(12, 0)]

    def test_functions_classes_and_imports_have_no_site(self) -> None:
        source = "import os\ndef f():\n    pass\nclass C:\n    pass\n"
        assert definition_sites(source, {"os", "f", "C"}) == {}

    def test_unparsable_source_has_no_sites(self) -> None:
        assert definition_sites("x = (", {"x"}) == {}


class TestLowerHint:
    @pytest.mark.parametrize(
        ("hint", "expected"),
        [
            ("int", "int"),
            ("List[str]", "list[str]"),
            ("Dict[str, List[int]]", "dict[str, list[int]]"),
            ("Set[int]", "set[int]"),
            ("FrozenSet[int]", "frozenset[int]"),
            ("Type[int]", "type[int]"),
            ("List[Union[int, str]]", "list[int | str]"),
            ("Optional[int]", "int | None"),
            ("Union[int, int]", "int"),
            ("NoneType", "None"),
            # Long fixed tuples loosen to a variadic tuple.
            ("Tuple[int, str]", "tuple[int, str]"),
            ("Tuple[int, str, int, str]", "tuple[int | str, ...]"),
            ("Tuple[int, ...]", "tuple[int, ...]"),
            (
                "Dict[str, Tuple[int, str, int, str]]",
                "dict[str, tuple[int | str, ...]]",
            ),
            # Narrowed literals widen to their declared type.
            ("Literal[1]", "int"),
            ("Literal[True]", "bool"),
            ('Literal[1, "a"]', "int | str"),
        ],
    )
    def test_typing_spellings_become_builtins(
        self, hint: str, expected: str
    ) -> None:
        node = lower_hint(hint)
        assert node is not None
        assert ast.unparse(node) == expected

    def test_not_an_expression(self) -> None:
        assert lower_hint("len(__obj: Sized) -> int") is None
        assert lower_hint("<class 'Foo'>") is None


class TestToAnnotation:
    def test_builtins_are_written_bare_with_refs(self) -> None:
        annotation = to_annotation("Dict[str, List[int]]", BUILTIN_REFS)
        assert annotation is not None
        assert annotation.repr == "dict[str, list[int]]"
        assert annotation.refs == {"dict", "str", "list", "int"}

    @pytest.mark.parametrize(
        "hint", ["DataFrame", "List[Foo]", "def f() -> int", "slider"]
    )
    def test_unresolvable_or_invalid_hints_are_dropped(
        self, hint: str
    ) -> None:
        assert to_annotation(hint, BUILTIN_REFS) is None

    def test_module_scope_names_are_allowed(self) -> None:
        allowed = BUILTIN_REFS | {"Foo", "Path"}
        assert to_annotation("List[Foo]", allowed).repr == "list[Foo]"
        assert to_annotation("Optional[Path]", allowed).repr == "Path | None"


class TestInferAnnotations:
    def test_inferred_types_land_in_signatures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                "x": [instance("builtins.int", "int")],
                "words": [instance("builtins.list", "List[str]")],
                "flag": [instance("builtins.bool", None)],
                "nothing": [instance("builtins.NoneType", "None")],
            }
        )
        source = generate(
            [
                "x = 1",
                "words = ['a']",
                "flag = True",
                "nothing = None",
                "print(x, words, flag, nothing)",
            ],
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert (
            "def _(flag: bool, nothing: None, words: list[str], x: int):"
            in source
        )

    def test_explicit_annotation_wins_and_is_not_probed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {"x": [instance("builtins.int", "int")]},
        )
        source = generate(
            ["x: float = 1", "y = 2", "print(x, y)"],
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(x: float, y):" in source
        # The backend was only asked about `y`; `x` is not a candidate.
        assert backend.inferred.keys() == {"x"}

    def test_several_definitions_form_a_union(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                "maybe": [
                    instance("builtins.NoneType", "None"),
                    instance("builtins.int", "int"),
                ],
                "same": [
                    instance("builtins.int", "int"),
                    instance("builtins.int", "int"),
                ],
            }
        )
        source = generate(
            [
                "maybe = None\nif maybe:\n    maybe = 1",
                "same = 1\nsame = 2",
                "print(maybe, same)",
            ],
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(maybe: None | int, same: int):" in source

    def test_hint_failure_falls_back_to_the_bare_class(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                # jedi raised on the hint for `[]`.
                "empty": [instance("builtins.list", None)],
                # The hint names a class that is not in scope.
                "frames": [instance("builtins.list", "List[DataFrame]")],
            }
        )
        source = generate(
            ["empty = []", "frames = [make()]", "print(empty, frames)"],
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(empty: list, frames: list):" in source

    @pytest.mark.parametrize("kind", ["function", "class", "module"])
    def test_non_instances_stay_bare(
        self, kind: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend({"thing": [Inferred("builtins.len", kind)]})
        source = generate(
            ["thing = len", "print(thing)"],
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(thing):" in source

    def test_shadowed_builtin_is_not_written(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend({"n": [instance("builtins.int", "int")]})
        source = generate(
            ["n = 1", "print(n)"],
            setup="int = 'shadowed'",
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(n):" in source

    def test_library_class_is_spelled_through_a_verified_alias(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                "df": [instance("pandas.core.frame.DataFrame", "DataFrame")],
                "arr": [instance("numpy.ndarray", "ndarray[Any, Any]")],
                "n": [instance("builtins.int", "int")],
            },
            classes={
                "pd.DataFrame": "pandas.core.frame.DataFrame",
                "np.ndarray": "numpy.ndarray",
            },
        )
        source = generate(
            [
                "df = pd.DataFrame()",
                "arr = np.zeros(3)",
                "n = 3",
                "print(df, arr, n)",
            ],
            setup="import numpy as np\nimport pandas as pd",
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(arr: np.ndarray, df: pd.DataFrame, n: int):" in source
        # Only aliases whose module contains the class are tried, and the
        # generic parameters are never written.
        assert backend.resolved == ["np.ndarray", "pd.DataFrame"]

    def test_unverified_spellings_are_omitted_not_quoted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                "df": [instance("pandas.core.frame.DataFrame", "DataFrame")],
                # A nested private path that no alias reaches.
                "stock": [
                    instance("marimo._plugins.ui._impl.input.slider", "slider")
                ],
                "n": [instance("builtins.int", "int")],
            },
            classes={},
        )
        source = generate(
            [
                "df = pd.DataFrame()",
                "stock = mo.ui.slider(1, 10)",
                "n = 3",
                "print(df, stock, n)",
            ],
            setup="import marimo as mo\nimport pandas as pd",
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(df, n: int, stock):" in source
        assert '"' not in source.split("def _(df, n: int, stock):")[0][-200:]
        assert backend.resolved == ["pd.DataFrame", "mo.slider"]

    def test_setup_import_of_the_class_itself_is_written_bare(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {"p": [instance("pathlib.Path", "Path")]},
            classes={"Path": "pathlib.Path"},
        )
        source = generate(
            ['p = Path(".")', "print(p)"],
            setup="from pathlib import Path",
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(p: Path):" in source

    def test_notebook_class_is_written_bare(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                "origin": [instance("__marimo_probe__.Point", "Point")],
                "points": [instance("builtins.list", "List[Point]")],
            },
            classes={"Point": "__marimo_probe__.Point"},
        )
        source = generate(
            [
                "class Point:\n    pass",
                "origin = Point()",
                "points = [Point()]",
                "print(origin, points)",
            ],
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(origin: Point, points: list[Point]):" in source

    def test_union_with_an_unspellable_member_is_dropped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                "value": [
                    instance("builtins.int", "int"),
                    instance("pandas.core.frame.DataFrame", "DataFrame"),
                ]
            }
        )
        source = generate(
            ["value = 1\nif value:\n    value = make()", "print(value)"],
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(value):" in source

    def test_off_never_builds_a_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def explode() -> None:
            raise AssertionError("the backend must not run")

        monkeypatch.setattr("marimo._ast.type_inference.JediBackend", explode)
        assert "def _(x):" in generate(
            ["x = 1", "print(x)"], infer_types="off"
        )

    def test_nothing_to_probe_skips_the_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def explode() -> None:
            raise AssertionError("the backend must not run")

        monkeypatch.setattr("marimo._ast.type_inference.JediBackend", explode)
        extraction, setup_cell = make_extraction(["x: int = 1", "print(x)"])
        assert (
            infer_annotations(
                extraction, setup_cell, filename=None, mode="jedi"
            )
            == {}
        )

    def test_notebook_directory_is_the_search_path(
        self, tmp_path: Path
    ) -> None:
        backend = FakeBackend({})
        extraction, setup_cell = make_extraction(["x = 1", "print(x)"])
        infer_annotations(
            extraction,
            setup_cell,
            filename=str(tmp_path / "nb.py"),
            mode="jedi",
            backend=backend,
        )
        assert backend.search_paths == [tmp_path]


class TestJediBackend:
    def test_infers_every_definition_and_drops_uninferable_names(
        self,
    ) -> None:
        source = (
            "count = 3\n"
            "maybe = None\n"
            "if count:\n"
            "    maybe = 1\n"
            "mystery = unknown_call()\n"
            "def restock(n):\n"
            "    return n\n"
            "fn = restock\n"
        )
        inferred = JediBackend().infer_definitions(
            source, {"count", "maybe", "mystery", "fn", "restock"}, None
        )
        assert inferred["count"] == [instance("builtins.int", "int")]
        assert [v.full_name for v in inferred["maybe"]] == [
            "builtins.NoneType",
            "builtins.int",
        ]
        assert inferred["fn"][0].kind == "function"
        # jedi has no answer for `unknown_call()`, and `restock` is bound by
        # `def`, which has no definition site.
        assert "mystery" not in inferred
        assert "restock" not in inferred

    def test_resolves_expressions_to_classes(self) -> None:
        source = "from pathlib import Path\nimport collections\n"
        resolved = JediBackend().resolve(
            source,
            ["Path", "collections.OrderedDict", "collections.nope"],
            None,
        )
        assert resolved[0] is not None
        assert resolved[0].kind == "class"
        assert resolved[0].full_name.endswith(".Path")
        assert resolved[1] is not None
        assert resolved[1].kind == "class"
        assert resolved[1].full_name == "collections.OrderedDict"
        assert resolved[2] is None


def test_infer_annotations_with_real_jedi() -> None:
    source = generate(
        [
            "class Point:\n    pass",
            "x = 1",
            "words = ['a', 'b']",
            "prices = {'a': 1.0}",
            "ratio = 1.5",
            "mixed = (1, 2, 4, 4, 'long type', 1, 1)",
            "flag = True",
            'p = Path(".")',
            "origin = Point()",
            "maybe = None\nif x:\n    maybe = 'a'",
            "helper = len",
            "print(x, words, prices, ratio, mixed, flag, p, origin, maybe)",
            "print(helper)",
        ],
        setup="from pathlib import Path",
    )
    for expected in [
        "flag: bool",
        "maybe: None | str",
        "mixed: tuple[int | str, ...]",
        "origin: Point",
        "p: Path",
        "prices: dict[str, float]",
        "ratio: float",
        "words: list[str]",
        "x: int",
    ]:
        assert expected in source
    # A function is not an instance, so it has no annotation.
    assert "def _(helper):" in source


@pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None
    or importlib.util.find_spec("pandas") is None,
    reason="numpy and pandas are required",
)
def test_library_classes_with_real_jedi() -> None:
    source = generate(
        [
            "df = pd.DataFrame({'a': [1]})",
            "col = df['a']",
            "prices = np.linspace(1.5, 2.5, 3)",
            "print(df, col, prices)",
        ],
        setup="import numpy as np\nimport pandas as pd",
    )
    assert "df: pd.DataFrame" in source
    assert "col: pd.Series" in source
    # NB. jedi infers `np.linspace` wrongly, and marimo writes what jedi
    # says. This pins the accepted behavior so a backend change is visible.
    assert "prices: tuple" in source


class TestBroadTypes:
    def test_object_and_any_are_dropped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                "blob": [instance("builtins.object", "object")],
                "maybe": [
                    instance("builtins.int", "int"),
                    instance("builtins.object", "object"),
                ],
                "items": [instance("builtins.list", "List[Any]")],
            }
        )
        source = generate(
            [
                "blob = object()",
                "maybe = 1\nif maybe:\n    maybe = object()",
                "items = [object()]",
                "print(blob, maybe, items)",
            ],
            setup="from typing import Any",
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(blob, items, maybe):" in source

    def test_union_wider_than_three_members_is_dropped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                "three": [
                    instance("builtins.int", "int"),
                    instance("builtins.NoneType", "None"),
                    instance("builtins.str", "str"),
                ],
                "four": [
                    instance("builtins.int", "int"),
                    instance("builtins.NoneType", "None"),
                    instance("builtins.str", "str"),
                    instance("builtins.bytes", "bytes"),
                ],
                # The collapsed tuple's element union is four wide.
                "record": [
                    instance("builtins.tuple", "Tuple[int, str, float, bytes]")
                ],
            }
        )
        source = generate(
            [
                "three = 1\nthree = None\nthree = 'a'",
                "four = 1\nfour = None\nfour = 'a'\nfour = b'a'",
                "record = (1, 'a', 2.0, b'a')",
                "print(three, four, record)",
            ],
            backend=backend,
            monkeypatch=monkeypatch,
        )
        assert "def _(four, record, three: int | None | str):" in source


class TestLineLength:
    def test_annotation_that_does_not_fit_its_line_is_dropped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                # `    x: list[str],` is 17 characters.
                "x": [instance("builtins.list", "List[str]")],
                # `    y: dict[str, list[int]],` is 28 characters.
                "y": [instance("builtins.dict", "Dict[str, List[int]]")],
            }
        )
        monkeypatch.setattr(
            "marimo._ast.type_inference.JediBackend", lambda: backend
        )
        source = codegen.generate_filecontents(
            ["x = ['a']", "y = {'a': [1]}", "print(x, y)"],
            ["_", "_", "_"],
            [CellConfig(), CellConfig(), CellConfig()],
            infer_types="jedi",
            line_length=20,
        )
        assert "def _(x: list[str], y):" in source

    def test_budget_counts_the_parameter_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = FakeBackend(
            {
                "a": [instance("builtins.int", "int")],
                "a_much_longer_name": [instance("builtins.int", "int")],
            }
        )
        monkeypatch.setattr(
            "marimo._ast.type_inference.JediBackend", lambda: backend
        )
        source = codegen.generate_filecontents(
            [
                "a = 1",
                "a_much_longer_name = 2",
                "print(a, a_much_longer_name)",
            ],
            ["_", "_", "_"],
            [CellConfig(), CellConfig(), CellConfig()],
            infer_types="jedi",
            # `    a: int,` is 11 characters; the long name needs 28.
            line_length=12,
        )
        assert "def _(a: int, a_much_longer_name):" in source
