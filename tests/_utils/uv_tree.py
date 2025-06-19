import dataclasses
import json
import pathlib

from marimo._server.models.packages import DependencyTreeNode
from marimo._utils.uv_tree import parse_uv_tree
from tests.mocks import snapshotter

SELF_DIR = pathlib.Path(__file__).parent
snapshot_test = snapshotter(__file__)


def serialize(tree: DependencyTreeNode) -> str:
    return json.dumps(dataclasses.asdict(tree), indent=2)


def test_complex_project_tree() -> None:
    # Generated from:
    #
    # ```sh
    # uv init blah && cd blah
    # uv add anywidget marimo
    # uv add --dev pytest
    # uv add --optional bar pandas
    # uv tree --no-dedupe
    # ```
    complex_project_tree = """bar v0.1.0
├── anywidget v0.9.18
│   ├── ipywidgets v8.1.7
│   │   ├── comm v0.2.2
│   │   │   └── traitlets v5.14.3
│   │   ├── ipython v9.3.0
│   │   │   ├── decorator v5.2.1
│   │   │   ├── ipython-pygments-lexers v1.1.1
│   │   │   │   └── pygments v2.19.1
│   │   │   ├── jedi v0.19.2
│   │   │   │   └── parso v0.8.4
│   │   │   ├── matplotlib-inline v0.1.7
│   │   │   │   └── traitlets v5.14.3
│   │   │   ├── pexpect v4.9.0
│   │   │   │   └── ptyprocess v0.7.0
│   │   │   ├── prompt-toolkit v3.0.51
│   │   │   │   └── wcwidth v0.2.13
│   │   │   ├── pygments v2.19.1
│   │   │   ├── stack-data v0.6.3
│   │   │   │   ├── asttokens v3.0.0
│   │   │   │   ├── executing v2.2.0
│   │   │   │   └── pure-eval v0.2.3
│   │   │   └── traitlets v5.14.3
│   │   ├── jupyterlab-widgets v3.0.15
│   │   ├── traitlets v5.14.3
│   │   └── widgetsnbextension v4.0.14
│   ├── psygnal v0.13.0
│   └── typing-extensions v4.14.0
├── marimo v0.14.0
│   ├── click v8.2.1
│   ├── docutils v0.21.2
│   ├── itsdangerous v2.2.0
│   ├── jedi v0.19.2
│   │   └── parso v0.8.4
│   ├── loro v1.5.1
│   ├── markdown v3.8.2
│   ├── narwhals v1.43.1
│   ├── packaging v25.0
│   ├── psutil v7.0.0
│   ├── pygments v2.19.1
│   ├── pymdown-extensions v10.15
│   │   ├── markdown v3.8.2
│   │   └── pyyaml v6.0.2
│   ├── pyyaml v6.0.2
│   ├── starlette v0.47.0
│   │   └── anyio v4.9.0
│   │       ├── idna v3.10
│   │       └── sniffio v1.3.1
│   ├── tomlkit v0.13.3
│   ├── uvicorn v0.34.3
│   │   ├── click v8.2.1
│   │   └── h11 v0.16.0
│   └── websockets v15.0.1
├── pandas v2.3.0 (extra: blah)
│   ├── numpy v2.3.0
│   ├── python-dateutil v2.9.0.post0
│   │   └── six v1.17.0
│   ├── pytz v2025.2
│   └── tzdata v2025.2
└── pytest v8.4.1 (group: dev)
    ├── iniconfig v2.1.0
    ├── packaging v25.0
    ├── pluggy v1.6.0
    └── pygments v2.19.1"""

    tree = parse_uv_tree(complex_project_tree)
    snapshot_test("complex_project_tree.json", serialize(tree))


def test_empty_project_tree() -> None:
    # Generated from:
    #
    # ```sh
    # uv init blah && cd blah
    # uv tree --no-dedupe
    # ```
    empty_project_tree = """bar v0.1.0"""
    tree = parse_uv_tree(empty_project_tree)
    snapshot_test("empty_project_tree.json", serialize(tree))


def test_simple_project_tree() -> None:
    # Generated from:
    #
    # ```sh
    # uv init blah && cd blah
    # uv add polars pandas
    # uv tree --no-dedupe
    # ```
    simple_project_tree = """bar v0.1.0
├── pandas v2.3.0
│   ├── numpy v2.3.0
│   ├── python-dateutil v2.9.0.post0
│   │   └── six v1.17.0
│   ├── pytz v2025.2
│   └── tzdata v2025.2
└── polars v1.31.0"""
    tree = parse_uv_tree(simple_project_tree)
    snapshot_test("simple_project_tree.json", serialize(tree))


def test_script_tree() -> None:
    # Generated from:
    #
    # ```sh
    # uv init --script blah.py
    # uv add --script polars pandas anywidget
    # uv tree --script blah.py --no-dedupe
    # ```
    script_tree = """polars v1.31.0
    pandas v2.3.0
    ├── numpy v2.3.0
    ├── python-dateutil v2.9.0.post0
    │   └── six v1.17.0
    ├── pytz v2025.2
    └── tzdata v2025.2
    anywidget v0.9.18
    ├── ipywidgets v8.1.7
    │   ├── comm v0.2.2
    │   │   └── traitlets v5.14.3
    │   ├── ipython v9.3.0
    │   │   ├── decorator v5.2.1
    │   │   ├── ipython-pygments-lexers v1.1.1
    │   │   │   └── pygments v2.19.1
    │   │   ├── jedi v0.19.2
    │   │   │   └── parso v0.8.4
    │   │   ├── matplotlib-inline v0.1.7
    │   │   │   └── traitlets v5.14.3
    │   │   ├── pexpect v4.9.0
    │   │   │   └── ptyprocess v0.7.0
    │   │   ├── prompt-toolkit v3.0.51
    │   │   │   └── wcwidth v0.2.13
    │   │   ├── pygments v2.19.1
    │   │   ├── stack-data v0.6.3
    │   │   │   ├── asttokens v3.0.0
    │   │   │   ├── executing v2.2.0
    │   │   │   └── pure-eval v0.2.3
    │   │   └── traitlets v5.14.3
    │   ├── jupyterlab-widgets v3.0.15
    │   ├── traitlets v5.14.3
    │   └── widgetsnbextension v4.0.14
    ├── psygnal v0.13.0
    └── typing-extensions v4.14.0"""

    tree = parse_uv_tree(script_tree)
    snapshot_test("script_tree.json", serialize(tree))


def test_empty_script_tree() -> None:
    # Generated from:
    #
    # ```sh
    # uv init --script blah.py
    # uv tree --script blah.py --no-dedupe
    # ```
    empty_script_tree = ""
    tree = parse_uv_tree(empty_script_tree)
    snapshot_test("empty_script_tree.json", serialize(tree))
