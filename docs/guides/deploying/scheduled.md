# Running marimo as a schedule job

marimo notebooks are plain Python files under the hood, so any system that can schedule a Python script can schedule a marimo notebook. This includes cron, [airflow](https://airflow.apache.org/) or [prefect](https://www.prefect.io/). You can even [pass variables](https://docs.marimo.io/guides/scripts/?h=command+line) from the command line to marimo notebooks, which makes them very versatile for this use-case.

## Github Actions

Instead of running CRON locally, you might be interested in running scheduled marimo notebooks as part of your [Github actions](https://docs.github.com/en/actions/reference/events-that-trigger-workflows#schedule) workflow. You can use the code below as a starting point. Note that this example does assume that you're using [inline dependencies](guides/package_management/inlining_dependencies). 

```yaml
name: Run marimo notebook every day at 09:00

on:
  schedule: '0 9 * * *'
jobs:
  scheduled:
jobs:
  run-marimo:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
      
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
        
    - name: Install uv
      uses: astral-sh/setup-uv@v3
      with:
        version: "latest"
    
    - name: Use uv to run notebook as normal script
      run: |
        uv run path/to/marimo_notebook.py
```

## Alternatives

For tools like Airflow and Prefect, you can also choose to reuse parts of a marimo notebook in larger Python batch jobs. Check the [docs on reusing functions](https://docs.marimo.io/guides/reusing_functions/) if you're interested in that. 

Alternatively, you may be interested in having specific cells in marimo run on an automated schedule as you have the notebook open. The simplest way to do that is to use the [mo.ui.refresh](https://docs.marimo.io/api/inputs/refresh/#marimo.ui.refresh) widget to manually specify how often a cell needs to rerun.

Finally, if you have very custom needs, you can always use 3rd party Python libraries (like [schedule](https://schedule.readthedocs.io/en/stable/index.html)) to set up something bespoke from your own code.