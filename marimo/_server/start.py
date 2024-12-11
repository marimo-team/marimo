def _print_network_access_message(host: str, port: int) -> None:
    """Print a message when the server is accessible on the local network."""
    if host == "0.0.0.0":
        logger.info("\nℹ️  Server is accessible on your local network at:")
        logger.info(f"   http://<your-ip-address>:{port}")
