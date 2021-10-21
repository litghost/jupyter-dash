from ipykernel.comm import Comm
import asyncio

__jupyter_config = {}
__jupyter_config_future = asyncio.Future()
__dash_comm = Comm(target_name="jupyter_dash")


@__dash_comm.on_msg
def _receive_message(msg):
    msg_data = msg.get("content").get("data")
    msg_type = msg_data.get("type", None)
    if msg_type == "base_url_response":
        __jupyter_config_future.set_result(msg_data)


async def _get_jupyter_config():
    __dash_comm.send({"type": "base_url_request"})

    global __jupyter_config
    __jupyter_config = await __jupyter_config_future


# This task will be complete once __jupyter_config is populated.
__jupyter_config_task = asyncio.create_task(_get_jupyter_config())


async def _request_jupyter_config(timeout=1):
    """Attempt to complete task to retrieve jupyter config.

    This coroutine will timeout after arg timeout seconds.
    This coroutine can be awaited multiple times in case time is too short.
    This coroutine is a no-op outside of Jupyter.

    """

    # Heavily inspired by implementation of CaptureExecution in the
    if __dash_comm.kernel is None:
        # Not in jupyter setting
        return

    try:
        await asyncio.wait_for(asyncio.shield(__jupyter_config_task), timeout=timeout)
    except asyncio.TimeoutError:
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

    if not __jupyter_config_future.done():
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
