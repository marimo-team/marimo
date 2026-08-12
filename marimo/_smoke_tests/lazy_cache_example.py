import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Lazy Cache Signing Smoke Test

    This notebook exercises the Ed25519 cache-signing feature built into
    `LazyLoader`. Signing is **automatic** when the `cryptography` package is
    installed — no configuration required.

    > **Prereq:** `uv sync --extra signing`

    On first run, marimo generates a per-user Ed25519 key and saves it to
    `~/.local/state/marimo/cache_signing_key.pem`.  Subsequent runs load the
    saved key and verify every cache entry before unpickling.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md("""
    ## 1 — Context-manager form (`mo.persistent_cache`)
    """)
    return


@app.cell(hide_code=True)
def _():
    with mo.persistent_cache("signing_demo_ctx", method="lazy"):
        ctx_result = sum(i**2 for i in range(100_000))

    mo.md(f"**ctx_result** = `{ctx_result}`")
    return


@app.cell(hide_code=True)
def _():
    mo.md("""
    ## 2 — Decorator form (`mo.persistent_cache`)
    """)
    return


@app.cell(hide_code=True)
def _():
    @mo.persistent_cache(method="lazy")
    def expensive(n: int) -> int:
        return sum(i**2 for i in range(n))


    dec_result = expensive(100_000)
    mo.md(f"**expensive(100 000)** = `{dec_result}`")
    return


@app.cell(hide_code=True)
def _():
    mo.md("""
    ## 3 — Where is the signing key?

    marimo resolves the key in this order:

    1. `MARIMO_CACHE_SIGNING_PRIVATE_KEY` env var
    2. `MARIMO_CACHE_SIGNING_PUBLIC_KEY` env var
    3. `<marimo_state_dir>/cache_signing_key.pem` — loaded or auto-generated
    """)
    return


@app.cell(hide_code=True)
def _():
    from marimo._utils.xdg import marimo_state_dir

    _key_path = marimo_state_dir() / "cache_signing_key.pem"
    mo.md(f"""
    **Key file:** `{_key_path}`

    **Exists:** `{_key_path.exists()}`
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md("""
    ## 4 — Custom key via env vars

    For shared infrastructure (e.g. a Redis cache written by CI and read by
    notebook users), set env vars before starting marimo:

    ```bash
    export MARIMO_CACHE_SIGNING_PRIVATE_KEY="$(cat private_key.pem)"
    # consumers — public key only:
    export MARIMO_CACHE_SIGNING_PUBLIC_KEY="$(cat public_key.pem)"
    ```

    Use `generate_keypair()` to create a fresh key pair:
    """)
    return


@app.cell(hide_code=True)
def _():
    from marimo._save.signing import generate_keypair

    _priv, _pub = generate_keypair()
    mo.md(f"""
    ```
    # private key (keep secret)
    {_priv[:64].strip()}...

    # public key (share with consumers)
    {_pub.strip()}
    ```
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md("""
    ## 5 — NumPy & Pandas: external serializers work with signing
    """)
    return


@app.cell(hide_code=True)
def _():
    import numpy as np

    with mo.persistent_cache("signed_numpy_demo", method="lazy") as _c:
        arr = np.random.rand(1_000)
        mean_val = arr.mean()

    # _c.cache_clear()
    mo.md(f"NumPy array (first 3): `{arr[:3]}`, mean=`{mean_val:.4f}` ✅")
    return


@app.cell(hide_code=True)
def _():
    import pandas as pd

    with mo.persistent_cache("signed_pandas", method="lazy") as _c:
        df = pd.DataFrame({"x": range(10), "y": [i**2 for i in range(10)]})

    # Leave the cache in place so a re-run exercises the signed-load + verify
    # path; uncomment to force a fresh write instead.
    # _c.cache_clear()
    mo.md(f"DataFrame shape: `{df.shape}` | head: `{df.head(2).to_dict()!r}` ✅")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
