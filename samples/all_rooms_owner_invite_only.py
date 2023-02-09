import asyncio
import logging.config
from pathlib import Path

from symphony.bdk.gen.pod_model.v3_room_attributes import V3RoomAttributes
from symphony.bdk.core.symphony_bdk import SymphonyBdk
from symphony.bdk.core.config.loader import BdkConfigLoader
from symphony_room_modifier import SymphonyRoomModifier

def _configure_logging(logging_config_file=None):
    if logging_config_file == None:
        logging_config_file = Path.joinpath(Path(__file__).parent.parent, 'resources', 'logging.conf')     
    logging.config.fileConfig(logging_config_file, disable_existing_loggers=False)
    
def _get_bdk_config(bdk_config_file=None):
    if bdk_config_file == None:
        bdk_config_file = Path.joinpath(Path(__file__).parent.parent, 'resources', 'config.yaml')
    return BdkConfigLoader.load_from_file(bdk_config_file)

async def _start(bdk_config, settings, streams=None, filter=None):
    async with SymphonyBdk(bdk_config) as _bdk:
        sym_room_modifier = await SymphonyRoomModifier.create(_bdk)
        logging.info("BDK Created for {} with username {}".format(sym_room_modifier.bot_info.id, sym_room_modifier.bot_info.username))
        results = await sym_room_modifier.update_all_rooms(settings)
        print(results)
        
if __name__=="__main__":
    _configure_logging()
    bdk_config = _get_bdk_config()
    streams=filter=None
    settings = V3RoomAttributes(members_can_invite=False)

    try:
        logging.info("Running bot application...")
        asyncio.run(_start(bdk_config, settings, streams, filter))
    except KeyboardInterrupt:
        logging.info("Ending bot application")