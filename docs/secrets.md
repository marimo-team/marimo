# Secret Management in Marimo

Marimo provides built-in functionality for securely managing secrets in your notebooks.

## Usage

```python
import marimo as mo

app = mo.App()

# Store a secret
app.set_secret("api_key", "my-secret-key")

# Retrieve a secret
api_key = app.get_secret("api_key")

# Delete a secret when no longer needed
app.delete_secret("api_key")
```

## Security

Secrets are stored securely using the system's native keyring service:
- macOS: Keychain
- Windows: Credential Locker
- Linux: Secret Service API/libsecret

## Best Practices

1. Never commit secrets to version control
2. Delete secrets when they're no longer needed
3. Use environment variables for development/testing
4. Rotate secrets regularly 