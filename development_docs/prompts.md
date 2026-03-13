# Prompts

## System prompts

Prompts are generated using the `Prompter` class in `marimo/_server/ai/prompts.py`.

### Snapshots

You can create snapshots of the prompts using the `snapshot` function in `tests/_server/ai/test_prompts.py`. These snapshots are checked into the repo, and you can use them to verify that the prompts have not changed. To run these snapshots, run:

```bash
hatch run +py=3.12 test-optional:test tests/_server/ai/test_prompts.py
```
