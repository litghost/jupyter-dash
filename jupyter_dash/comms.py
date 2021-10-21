from ipykernel.comm import Comm
import asyncio
import http.server
import socketserver
import json
from json import JSONDecodeError
from http import HTTPStatus
import time
import logging

__jupyter_config = {}
__dash_comm = Comm(target_name="jupyter_dash")


MAX_LENGTH = 512


def _set_jupyter_config(config):
    global __jupyter_config
    __jupyter_config = config


class OneRequestServer(http.server.BaseHTTPRequestHandler):
    """This is single purpose HTTP server thats sole purpose is to receive one AJAX.

    The one AJAX request should be a JSON message from the JupyterDash browser plugin
    in response to the Comm message "base_url_request_ajax".

    """

    error_content_type = "application/json"

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        super().__init__(*args, **kwargs)

    def send_bad_request(self, body):
        self.send_response(HTTPStatus.BAD_REQUEST)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_POST(self):
        if self.headers["Content-Type"] != "application/json":
            self.send_bad_request(
                {
                    "error": (
                        'Content-Type must be "application/json", was "{}"'
                    ).format(self.headers["Content-Type"])
                }
            )
            return

        content_length = int(self.headers["Content-Length"])
        if content_length > MAX_LENGTH:
            self.send_bad_request(
                {
                    "error": ("Content-Length must be less than {}, got {}").format(
                        self.headers["Content-Length"], MAX_LENGTH
                    )
                }
            )
            return

        post_data = self.rfile.read(content_length)

        try:
            data = post_data.decode()
        except UnicodeError:
            self.send_bad_request({"error": "Content must be valid UTF-8"})
            return

        try:
            msg = json.loads(data)
        except JSONDecodeError:
            self.send_bad_request({"error": "Content must be valid JSON"})
            return

        for field in ["type", "server_url", "base_subpath", "frontend"]:
            if field not in msg:
                self.send_bad_request({"error": "Key {} was not found".format(field)})
                return

        _set_jupyter_config(msg)

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        response = {}
        self.wfile.write(json.dumps(response).encode())

        self.server.serving = False

    def handle_timeout(self):
        pass

    def log_message(self, format, *args, **kwargs):
        self.logger.info(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % args)
        )


async def _request_jupyter_config(timeout=1):
    """Attempt to complete task to retrieve jupyter config.

    """

    # Re-open the comm in case the frontend connection was lost (e.g. tab closed or
    # refreshed).
    __dash_comm.open()

    # Start a server to receive the response from the browser plugin.
    with socketserver.TCPServer(("", 0), OneRequestServer) as server:
        server.timeout = 0.100
        port = server.server_address[1]

        # Now that socket is open, ask for AJAX request
        __dash_comm.send({"type": "base_url_request_ajax", "port": str(port)})

        if timeout is not None:
            timeout_time = time.time() + timeout

        server.serving = True

        while server.serving:
            server.handle_request()

            if timeout is not None:
                if time.time() > timeout_time:
                    break

        if server.serving:
            # If the server is still serving, never got the reply!
            raise RuntimeError(
                (
                    'Jupyter config not ready, re-run "await '
                    'JupyterDash.infer_jupyter_proxy_config()"'
                )
            )


def get_jupyter_config():
    global __jupyter_config
    if __dash_comm.kernel is None:
        # Not in jupyter setting
        return {}

    if not __jupyter_config:
        raise RuntimeError(
            (
                'Jupyter config not ready, re-run "await '
                'JupyterDash.infer_jupyter_proxy_config()"'
            )
        )

    return __jupyter_config


def dash_send(message):
    # Re-open the comm in case the frontend connection was lost (e.g. tab closed or
    # refreshed).
    __dash_comm.open()
    __dash_comm.send(message)
