Loosen pillow pin in test-optional to avoid source builds

The `~=10.4.0` constraint forced pillow 10.4.x which lacks prebuilt
wheels for some platform/Python combos, causing compilation failures
when jpeg headers aren't available. Using `>=10.4.0` lets uv pick a
newer version with wheels.
