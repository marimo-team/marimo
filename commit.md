Replace attach/detach extension with `session.scoped` context manager

The previous API required callers to manually pair `attach_extension` and
`detach_extension` in try/finally blocks. Every caller followed the exact
same pattern, and forgetting the finally would leak extensions. A context
manager eliminates this class of bug entirely.

```python
with session.scoped(listener):
    # listener is attached for the duration of this block
    ...
```
