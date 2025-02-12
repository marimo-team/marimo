import marimo as mo

# Create a new cell
sm = mo.secret_manager()

# test setting a secret
sm.set_secret("test_key")

# Test retrieving the secret
secret = sm.get_secret("test_key")
txt = f"Retrieved secret: {secret}"
mo.md(txt)
print(txt)

# Test overriding a secret
sm.set_secret("test_key", "overridden_value")
secret = sm.get_secret("test_key") 
txt = f"Overridden secret: {secret}"
mo.md(txt)
print(txt)

# Clean up
sm.delete_secret("test_key")
secret = sm.get_secret("test_key")
txt = f"Deleted secret: {secret}"
mo.md(txt)
print(txt)