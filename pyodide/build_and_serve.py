import http.server
import os
import socketserver
import subprocess
import threading
from posixpath import join

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer


class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "X-Requested-With, Content-Type"
        )
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.end_headers()


class WheelBuilderHandler(PatternMatchingEventHandler):
    patterns = ["*.py"]  # Watch for changes in Python files

    def on_any_event(self, event):
        print(f"Change detected: {event.src_path}")
        print("Building wheel...")
        subprocess.run(["python3", "-m", "build"])
        print("Wheel built successfully.")


def serve():
    with socketserver.TCPServer(("", 8000), CORSHTTPRequestHandler) as httpd:
        httpd.allow_reuse_address = True
        print("Serving at http://localhost:8000")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        httpd.server_close()
        print("Server stopped.")


cwd = os.getcwd()

if __name__ == "__main__":
    # Start the HTTP server in a separate thread
    threading.Thread(target=serve, daemon=True).start()

    # Set up the watchdog observer to watch the current directory
    observer = Observer()
    path = join(cwd, "marimo")
    observer.schedule(WheelBuilderHandler(), path=path, recursive=True)
    observer.start()

    print("Watching for changes. Press Ctrl+C to stop.")
    print(f"Watching directory: {path}")
    try:
        while True:
            observer.join(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
