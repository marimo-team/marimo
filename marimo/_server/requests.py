from git import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import HTTPConnection


def get_base_url(request: "HTTPConnection") -> str:
    """Get the original URL of the request."""
    scheme = (
        request.headers.get("x-forwarded-proto")
        or request.headers.get("x-forwarded-protocol")
        or request.headers.get("x-scheme")
        or request.headers.get("cloudfront-forwarded-proto")
        or request.base_url.scheme
    )

    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("x-original-host")
        or request.headers.get("host")
        or request.base_url.hostname
    )

    # Handle port if needed
    port = request.headers.get("x-forwarded-port")
    if port and port not in ["80", "443"]:
        if host and ":" not in host:
            host = f"{host}:{port}"

    path = request.base_url.path
    query = request.base_url.query

    original_url = f"{scheme}://{host}{path}"
    if query:
        original_url += f"?{query}"

    return original_url
