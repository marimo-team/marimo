# Stat

/// marimo-embed

```python
@app.cell
def __():
    active_users = mo.stat(
        value="1.2M", 
        label="Active Users", 
        caption="12k from last month", 
        direction="increase"
    )

    revenue = mo.stat(
        value="$4.5M", 
        label="Revenue", 
        caption="8k from last quarter", 
        direction="increase"
    )
    
    conversion = mo.stat(
        value="3.8", 
        label="Conversion Rate", 
        caption="0.5 from last week", 
        direction="decrease",
    )
    
    mo.hstack([active_users, revenue, conversion], justify="center", gap="2rem")
    return
```

///

::: marimo.stat
