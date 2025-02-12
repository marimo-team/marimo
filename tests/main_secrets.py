import marimo as mo

# Create a new cell
app = mo.App()

# Test setting a secret with user input
app.set_secret("test_key")

# Test retrieving the secret
secret = app.get_secret("test_key")
txt = f"Retrieved secret: {secret}"
mo.md(txt)
print(txt)

# Test overriding a secret
app.set_secret("test_key", "overridden_value")
secret = app.get_secret("test_key") 
txt = f"Overridden secret: {secret}"
mo.md(txt)
print(txt)

# Clean up
app.delete_secret("test_key")
secret = app.get_secret("test_key")
txt = f"Deleted secret: {secret}"
mo.md(txt)
print(txt)