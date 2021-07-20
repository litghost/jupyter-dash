from ipykernel.comm import Comm
import asyncio

_jupyter_config = {}
_jupyter_config_future = asyncio.Future()
_dash_comm = Comm(target_name='jupyter_dash')

@_dash_comm.on_msg
def _receive_message(msg):
    msg_data = msg.get('content').get('data')
    msg_type = msg_data.get('type', None)
    if msg_type == 'base_url_response':
        _jupyter_config_future.set_result(msg_data)

async def _get_jupyter_config():
    _dash_comm.send({
                'type': 'base_url_request'
            })

    global _jupyter_config
    _jupyter_config = await _jupyter_config_future

_jupyter_config_task = asyncio.create_task(_get_jupyter_config())
    
async def _request_jupyter_config(timeout=2):
    await asyncio.wait_for(asyncio.shield(_jupyter_config_task), timeout=timeout)
