# Review instructions

- Existing notebooks must keep loading, and saving must preserve them (`marimo/_ast`).
- Check changes to which cells run and in what order (`marimo/_ast`, `marimo/_runtime/dataflow`).
- Server endpoints must not allow file access or code execution beyond the session's permissions.
- Don't report formatting, generated files, or lockfiles.
