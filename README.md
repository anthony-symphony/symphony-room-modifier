# Symphony Room Modifier

This module can be used to easily modify many rooms at once by passing it either a list of streams to modify or a filter, along with the settings you want to modify it to. Samples can be found in the [samples folder](samples).

The [module](#usage-as-a-module) utilizes the Symphony Python BDK and configuration of the BDK can be found here.\
Also included is a [command line parser](#usage-via-command-line) to simplify modifying rooms via the command line.
<br/>


## Limitations

- Symphony only allows you to modify rooms that were created on your own instance and are currently active. If you try to modify a room that was created by another firm, it will fail. By default the update_all_rooms function filters out all rooms that are created externally or inactive.
- Symphony only allows you to modify rooms that you are an owner of. As such, please note when this library updates a room, other members will see a bot get added, change the info and remove itself if it is not already in the room. The bot will take care of demoting/removing itself from the room as necessary to keep the state of the room before chaning the settings.

## Requirements

- This module requires a Service Account with the "User Provisioning" role. This role is required to list all the streams on the Symphony instance. It is also required to allow the bot to add itself to any room so it can modify the settings.
<br/><br/>

# Usage as a Module  

1. Run `pip install -r requirements.txt` to install the necessary python modules.
2. Copy the symphony_room_modifier.py to your project and import it.
3. Create a SymphonyBDK in your script. Information on how to do that can be found in the Symphony Python BDK repo. Make sure the bot has `User Provisioning` role.
4. Create the SymphonyRoomModifier by passing the BDK into `SymphonyRoomModifier.create(bdk)`

## Sample:
<hr/>

The below example modifies all rooms to allow only room owners the ability to add more members to the room.
```
from symphony_room_modifier import SymphonyRoomModifier

async def start():
    bdk_config_file = Path.joinpath(Path(__file__).parent.parent, 'resources', 'config.yaml')
    bdk_config = BdkConfigLoader.load_from_file(bdk_config_file)
    settings = V3RoomAttributes(members_can_invite=False)
    async with SymphonyBdk(bdk_config) as bdk:
        sym_room_modifier = await SymphonyRoomModifier.create(bdk)
        logging.info("BDK Created for {} with username {}".format(sym_room_modifier.bot_info.id, sym_room_modifier.bot_info.username))
        results = await sym_room_modifier.update_all_rooms(settings)
        print(results)

asyncio.run(start())
```

# Usage via Command Line

To simplify modifying rooms a command line parser is also included in this project. To use it just call the script with ```python ./modify_rooms.py``` along with the mode and arguments you would like to use.

## Setup
1. If not already done, create a Service Account with the `User Provisioning` role. 
2. Configure your [config.yaml](samples/config.yaml) as necessary and place it in the same directory as `modify_rooms.py`. More information on configuration properties can be found in the [Symphony Python BDK Guide](https://symphony-bdk-python.finos.org/markdown/configuration.html))
3. Configure your [logging.conf](samples/logging.conf) if you would like to specify logging and place it in the root directory with `modify_rooms.py`. If no logging.conf is found, it will output DEBUG logs to `modify_rooms.log`

## Mode

The script has 3 modes:
- [csv](#csv-mode) : Modify rooms based on CSV files. ('csv -h' for more info.)
- [single](#single-mode) : Modify a single room based on settings supplied. (Run 'single -h' for more info.)
- [all](#all-mode) : Modify all modifiable rooms. ('all -h for more info.)

## Single Mode
Single mode modifies a single stream that you will pass with ```-s``` along with the settings you want to change. Please see [Available Modifiable Settings](#available-modifiable-settings) for the settings you can change.

The below for example will modify the stream `SzWvudXb1X5QPjFRvb7umX___pqnIpcmdA` so that all members can add people to the room.
```
python ./modify_rooms.py single -s SzWvudXb1X5QPjFRvb7umX___pqnIpcmdA --membersCanInvite true
```

## All Mode
All mode modifies all streams that are modifiable to the [settings](#available-modifiable-settings) specified in your arguments. This means any room that was created from your own Symphony Instance and are currently active. 

You can also narrow down the rooms modified with the following flags:

Scope (Modifies both internal and external rooms if not specified):
- --internal: Modify only Internal Rooms.
- --external: Modify only External Rooms. 
    
Privacy (Modifies both public and private rooms if not specified):
- --public: Modify only Public Rooms. (Public rooms can only be internal.)
- --private: Modify only Private Rooms.

<br/>
The below for example will modify all internal private rooms so that anyone can add members and new members can't see the history of the chat.

```
python ./modify_rooms.py all --membersCanInvite true --viewHistory false --internal --private
```

## CSV Mode

### **Exporting Rooms**

<hr/>

CSV mode allows you to input a CSV file and modify each room as defined by the row. You can get a list of current rooms in the format expected with `--list`

`--listall` is also available if you want to export rooms that are not modifiable as well.

The following arguments are available while exporting:
- -l, --list: Generate a CSV file of all Rooms that are modifiable. (Active Rooms that were created by your Symphony instance.)
- -a, --listall: Generate a CSV file of all Rooms including ones that are not modifiable.
- -x, --extended: Include non-modifiable properties in CSV export.
- -o, --output: CSV File to output list of streams (--list/--listall) or results(--update).

Just as in "all" mode you can narrow down the rooms you export when using `--list` to the CSV with the internal/external and public/private flags. However, you can also narrow down by origin and status. 

**Note: you can not modify rooms with external origin or inactive status but, it may be useful to have an export of it.**

Scope (Exports both internal and external rooms if not specified):
- --internal: Export Internal Rooms.
- --external: Export External Rooms.

Privacy (Exports both public and private rooms if not specified)
- --public: Export public rooms.
- --private: Expot private rooms.

Origin (Export rooms created internally and externally if not specified. --list will only export rooms of internal origin and this flag will be ignored)
- --internalOrigin: Export rooms created by an internal user.
- --externalOrigin: Export rooms created by an external user.

Status (Export active an inactive rooms if not specified. --list will only export active rooms and this flag will be ignored)
- --active: Export active rooms.
- --inactive: Export inactive rooms.

The below example will export all internal rooms and will include non-modifiable settings to the output file `test_output.csv`

```
python ./modify_rooms.py csv --list --internal -x --output test_output.csv
```
<hr/>

### **Updating Rooms**

You can update rooms by passing in a CSV file with the stream settings.\
More information on each setting can be found in the available commandline settings section.\
If you would like to unset description or pinnedMessageId, set it to `""`\

You may also pass a list of streams with a streamId in each line. If doing so, you must specify at least one [setting](#available-modifiable-settings) to modify. Any settings in the CSV will be ignored if a setting is specified in the command line.

- -i, --input: Input CSV File of rooms to update.
- -o, --output: CSV File to output list of streams (--list/--listall) or results(--update).
- -x, --extended: Include non-modifiable properties in CSV export.

**A sample of the CSV input can be found [here](samples/sample.csv). Please note this is the same as the extended output. Any marked with (X) in the column are non-modifiable but, are included for your reference.**

The below example will update the rooms to match the CSV file `input.csv` and output the results to `results.csv`:
```
python ./modify_rooms.py csv -i input.csv -o results.csv
```

## Available Modifiable Settings

These are the available settings you can modify. If not set, the setting will not be modified. If any are specified for CSV mode, settings in the CSV file will be ignored.
    
- --membersCanInvite (true/false): If true, anyone can add room members. If false, only owners can.
- --discoverable (true/false): If true, this chat room is searchable by anyone. If false only members can.)
- --copyProtected (true): If true, copying from room is disabled. (Can only be set to true. Once room is set to true it can't be set back to false.)
- --viewHistory (true/false): If true, new members can view the room chat history of the room.

The following are only available for single stream mode:
    
- --name (string): Name of the stream.
- --description (string): Description of the stream. Set to "" to unset. (ex: --description '""')
- --pinnedMessageId (string): MessageID you would like to pin for this room. Set to "" to unset (ex: --pinnedMessageId '""')