'''
Command line wrapper for symphony_room_modifier module. All functionality documented in the HELP TEXTS below.
Following files must be included in same directory
'''

__author__ = 'Anthony Lee'
__maintainer__ = 'Anthony Lee'
__email__ = 'anthony.lee@symphony.com'\

import asyncio
import logging, logging.config
import sys
import getopt

from pathlib import Path
from datetime import datetime

from symphony.bdk.core.symphony_bdk import SymphonyBdk
from symphony.bdk.core.config.loader import BdkConfigLoader
from symphony.bdk.gen.pod_model.v2_admin_stream_filter import V2AdminStreamFilter
from symphony.bdk.gen.pod_model.v2_admin_stream_type import V2AdminStreamType
from symphony.bdk.gen.pod_model.v3_room_attributes import V3RoomAttributes
from symphony_room_modifier.symphony_room_modifier import SymphonyRoomModifier

log = logging.getLogger("modify_rooms")
#Help text and help functions
HELP_ROOT = '''
    csv: Modify rooms based on CSV files. ('csv -h' for more info.)
    single: Modify a single room based on settings supplied. (Run 'single -h' for more info.)
    all: Modify all modifiable rooms. ('all -h for more info.)
'''
HELP_CSV = '''
Input file can be either be a CSV file with new settings or a list. If it is a list you must specify at least one setting you would like to modify in your arguments.
    
    -l, --list: Generate a CSV file of all Rooms that are modifiable. (Active Rooms that were created by your Symphony instance.)
    -a, --listall: Generate a CSV file of all Rooms including ones that are not modifiable.
    -x, --extended: Include non-modifiable properties in CSV export.
    -i, --input: Input File of rooms to update.
    -o, --output: CSV File to output list of streams (--list/--listall) or results(--input).
    
    You can modify the scope of rooms exported for --list/--listall to modify scope of export to include non-modifiable streams:
    
    Scope (Exports both internal and external rooms if not specified):
        --internal: Export Internal Rooms.
        --external: Export External Rooms.
    
    Privacy (Exports both public and private rooms if not specified):
        --public: Export public rooms.
        --private: Expot private rooms.
    
    Origin (Export rooms created internally and externally if not specified. --list will only export rooms of internal origin and this flag will be ignored)
        --internalOrigin: Export rooms created by an internal user.
        --externalOrigin: Export rooms created by an external user.
    
    Status (Export active an inactive rooms if not specified. --list will only export active rooms and this flag will be ignored)
        --active: Export active rooms.
        --inactive: Export inactive rooms.
    
''' 
HELP_COMMON_AVAILABLE_ROOM_SETTINGS = '''These are the available settings you can modify. If not set, the setting will not be modified. If any are specified for CSV mode, settings in CSV will be ignored.
    
    --membersCanInvite (true/false): If true, anyone can add room members. If false, only owners can.
    --discoverable (true/false): If true, this chat room is searchable by anyone. If false only members can.)
    --copyProtected (true): If true, copying from room is disabled. (Can only be set to true. Once room is set to true it can't be set back to false.)
    --viewHistory (true/false): If true, new members can view the room chat history of the room.
'''
HELP_SINGLE_ONLY_ROOM_SETTINGS ='''The following are only available for single stream mode:
    
    --name (string): Name of the stream.
    --description (string): Description of the stream. Set to "" to unset. (ex: --description '""')
    --pinnedMessageId (string): MessageID you would like to pin for this room. Set to "" to unset (ex: --pinnedMessageId '""')
'''
HELP_SINGLE_MODE = 'Specify the stream ID with -s followed by settings you want to modify. You must specify at least one room setting listed below.\n'
HELP_ALL_MODE = '''
Modify all modifiable streams (Active rooms that were created from your Symphony instance.
    
Scope (Modifies both internal and external rooms if not specified):
    --internal: Modify only Internal Rooms.
    --external: Modify only External Rooms. 
    
Privacy (Modifies both public and private rooms if not specified):
    --public: Modify only Public Rooms. (Public rooms can only be internal.)
    --private: Modify only Private Rooms.
    
You must specify at least one room setting listed below'''

HELP_CSV_TOO_MANY_MODES = 'You can only specify one of of: --list, --listall, or --input'
HELP_CSV_NO_MODE_SELECTED = 'You must specify one of: --list, --listall, or --input.'

def print_help():
    print(HELP_ROOT)
    
def print_csv_help():
    print(HELP_CSV)
    print_available_settings_common()
    
def print_csv_too_many_modes():
    print(HELP_CSV_TOO_MANY_MODES)

def print_csv_no_mode_selected():
    print()
def print_single_help():
    print(HELP_SINGLE_MODE)
    print_available_settings_common()
    print_available_settings_single()

def print_all_help():
    print(HELP_ALL_MODE)
    print_available_settings_common()
    
def print_available_settings_common():
    print(HELP_COMMON_AVAILABLE_ROOM_SETTINGS)

def print_available_settings_single():
    print(HELP_SINGLE_ONLY_ROOM_SETTINGS)

#End Help Printout Functions

COMMON_AVAILABLE_ROOM_ARGS = ['membersCanInvite=', 'discoverable=', 'copyProtected=', 'viewHistory=']
SINGLE_ONLY_AVAILABLE_ROOM_ARGS = ['name=', 'description=', 'pinnedMessageId=']
ALL_AVAILABLE_ROOM_ARGS = COMMON_AVAILABLE_ROOM_ARGS + SINGLE_ONLY_AVAILABLE_ROOM_ARGS

COMMON_AVAILABLE_ROOM_SETTINGS = ['membersCanInvite', 'discoverable', 'copyProtected', 'viewHistory']
SINGLE_ONLY_AVAILABLE_ROOM_SETTINGS = ['name', 'description', 'pinnedMessageId']
ALL_AVAILABLE_ROOM_SETTINGS = COMMON_AVAILABLE_ROOM_SETTINGS + SINGLE_ONLY_AVAILABLE_ROOM_SETTINGS

COMMON_FILTER_ROOM_FLAGS = ['internal', 'external', 'public', 'private']
CSV_ONLY_FITLER_ROOM_FLAGS = ['internalOrigin', 'externalOrigin', 'active', 'inactive']
ALL_AVAILABLE_FILTER_ROOM_FLAGS = COMMON_FILTER_ROOM_FLAGS + CSV_ONLY_FITLER_ROOM_FLAGS

#Command Line Parsing
#Command Line Parser for 'single' mode.
def single_mode(argv):
    log.debug('Single Mode')
    if len(argv) == 0:
        print_single_help()
        exit()
    
    valid_long_args = ['help', 'stream='] + ALL_AVAILABLE_ROOM_ARGS
    try:
        opts, args = getopt.getopt(argv, 'hs:',valid_long_args)
    except Exception as err:
        handle_arg_errors(err, 'single')
        
    stream_id = ''
    settings = None
    for opt, arg in opts:
        stripped_opt = opt.lstrip('-')
        if opt in ('-h', '--help'):
            print_single_help()
            exit()
        if opt in ('-s', '--stream'):
            stream_id = arg
        elif stripped_opt in ALL_AVAILABLE_ROOM_SETTINGS:
            settings = parse_room_settings(settings, stripped_opt, arg, True)
    
    log.info('Modifying stream {} with settings: {}'.format(stream_id, settings))
    if settings is not None:
        try:
            asyncio.run(update_single_room(stream_id,settings))
        except KeyboardInterrupt:
            log.info('Keyboard interrupt detected. Ending modification of stream.')
    else:
        log.error('You must specify at least one setting in single mode.')

#Command Line Parser for 'all' mode
def all_mode(argv):
    log.debug('All Mode')
    if len(argv) == 0:
        print_all_help()
        exit()
    
    valid_long_args = ['help'] + COMMON_AVAILABLE_ROOM_ARGS + COMMON_FILTER_ROOM_FLAGS
    
    try:
        opts, args = getopt.getopt(argv, 'h',valid_long_args)
    except Exception as err:
        handle_arg_errors(err, 'all')
    
    settings:V3RoomAttributes = None
    filter_flags = initialize_filter_flags()
    for opt, arg in opts:
        stripped_opt = opt.lstrip('-')
        if opt in ('-h', '--help'):
            print_all_help()
            exit()
        elif stripped_opt in COMMON_FILTER_ROOM_FLAGS:
            filter_flags = parse_filter_settings(filter_flags, stripped_opt, arg) 
        elif stripped_opt in COMMON_AVAILABLE_ROOM_SETTINGS:
            settings = parse_room_settings(settings, stripped_opt, arg, False)
        
    stream_filter = create_stream_filter(filter_flags,settings)
    
    if (settings is not None):
        try:
            asyncio.run(update_all_rooms(stream_filter, settings))
        except KeyboardInterrupt:
            log.info('Keyboard interrupt detected. Ending modification of streams.')
    else:
        log.error('You must specify at least one setting in all mode.')
        
#Command Line Parser for 'csv' mode.
def csv_mode(argv):
    log.debug('CSV Mode')
    if len(argv) == 0:
        print_csv_help()
        exit()
    
    filter_flags = initialize_filter_flags()
    
    valid_long_args = ['help', 'listall', 'list', 'input=', 'ouput='] + ALL_AVAILABLE_ROOM_ARGS + ALL_AVAILABLE_FILTER_ROOM_FLAGS
    opts, args = getopt.getopt(argv, 'hlxi:o:', valid_long_args)
    
    input_arg = ''
    output_arg = ''
    mode = {}
    mode['list_all'] = False
    mode['list_modifiable'] = False
    mode['update'] = False
    export_non_modifiable = False
    settings:V3RoomAttributes = None
    
    for opt, arg in opts:
        stripped_opt = opt.lstrip('-')
        if opt in ('-h', '--help'):
            print_csv_help()
            exit()
        elif opt == '--list':
            if (mode['list_all'] or mode['update']):
                print_csv_too_many_modes()
                exit()
            else:
                mode['list_modifiable'] = True
        elif opt == '--listall':
            if (mode['list_modifiable'] or mode['update']):
                print_csv_too_many_modes()
                exit()
            else:
                mode['list_all'] = True
        elif opt in ('-x', '--extended'):
            export_non_modifiable = True
        elif opt in ('-i', '--input'):
            if (mode['list_modifiable'] or mode['list_all']):
                print_csv_too_many_modes()
                exit()
            mode['update'] = True
            input_arg = arg
        elif opt in ('-o', '--outputfile'):
            output_arg = arg

        elif stripped_opt in ALL_AVAILABLE_FILTER_ROOM_FLAGS:
            filter_flags = parse_filter_settings(filter_flags, stripped_opt, arg) 
        elif stripped_opt in COMMON_AVAILABLE_ROOM_SETTINGS:
            settings = parse_room_settings(settings, stripped_opt, arg, False)
            
    if (mode['list_all'] or mode['list_modifiable'] or mode['update']):
        stream_filter = create_stream_filter(filter_flags, settings)
        if (mode['list_modifiable']):
            stream_filter.status='ACTIVE'
            stream_filter.origin='INTERNAL'
        try:
            output_file = get_output_file_path(output_arg)
            if mode['update']:
                input_file = get_input_file_path(input_arg)
                asyncio.run(update_rooms_from_csv(input_file, output_file, settings, export_non_modifiable))
            else:
                asyncio.run(list_rooms_csv(stream_filter, output_file, export_non_modifiable))
        except KeyboardInterrupt:
            log.info('Keyboard Interrupt detected. Stopping export of streams to CSV file.')
        

async def list_rooms_csv(stream_filter, output_file, export_non_modifiable=False):
    async with SymphonyBdk(get_bdk_config()) as bdk:
        sym_room_modifier = await SymphonyRoomModifier.create(bdk)
        await sym_room_modifier.export_rooms_to_csv(stream_filter, output_file, export_non_modifiable)
        
async def update_rooms_from_csv(input_file, output_file=None, settings=None, export_non_modifiable = False):
    async with SymphonyBdk(get_bdk_config()) as bdk:
        sym_room_modifier = await SymphonyRoomModifier.create(bdk)
        await sym_room_modifier.update_rooms_from_csv(input_file, output_file, settings, export_non_modifiable)
    
#Shared method to modify settings based on command line arguments
def parse_room_settings(settings, flag, arg, is_single_mode=False):
    if settings is None:
        settings = V3RoomAttributes()
    if arg == '""' or arg == "''":
        arg = ''
    try:
        if flag == 'membersCanInvite':
            settings.members_can_invite = parse_bool(arg)
        elif flag == 'discoverable':
            settings.discoverable = parse_bool(arg)
        elif flag == 'copyProtected':
            settings.copy_protected = parse_bool(arg)
        elif flag == 'viewHistory':
            settings.view_history = parse_bool(arg)
        elif flag in SINGLE_ONLY_AVAILABLE_ROOM_SETTINGS:
            if not is_single_mode:
                log.error('{0} can only be used in single mode. Ignoring {0}', flag)
            elif flag == 'name':
                settings.name = arg
            elif flag == 'description':
                settings.description = arg
            elif flag == 'pinnedMessageId':
                settings.pinned_message_id = arg               
    except ValueError:
        log.error('{} set to {}. Expected {}', flag, arg, '[true/false]')     
    return settings

def parse_filter_settings(filter_flags, flag, arg):
    filter_flags[flag] = True
    return filter_flags

#Shared method to modify filter based on command line arguments and settings:
def create_stream_filter(filter_flags, settings=None):
    stream_filter = V2AdminStreamFilter()
        
    if filter_flags['internal'] != filter_flags['external']:
        if filter_flags['internal']:
            stream_filter.scope = 'INTERNAL'
        elif filter_flags['external']:
            stream_filter.scope = 'EXTERNAL'
            
    if filter_flags['internalOrigin'] != filter_flags['external']:
        if filter_flags['internal']:
            stream_filter.origin = 'INTERNAL'
    elif filter_flags['externalOrigin']:
            stream_filter.origin = 'EXTERNAL'

    if filter_flags['public'] != filter_flags['private']:
        if filter_flags['public']:
            stream_filter.privacy = 'PRIVATE'
        elif filter_flags['private']:
            stream_filter.privacy = 'PUBLIC'
    
    if filter_flags['active'] != filter_flags['inactive']:
        if filter_flags['active']:
            stream_filter.status = 'ACTIVE'
        elif filter_flags['inactive']:
            stream_filter.status = 'INACTIVE'
       
    if settings is not None: 
        if settings.copy_protected is not None:
            log.info('Copy Protected flag can only be used on internal rooms. Chaning scope to internal only.')
            stream_filter.scope = 'INTERNAL'
        
        if settings.discoverable is not None:
            log.info('Discoverable flag can only be set on internal Private rooms. Changing scope to Internal, Private rooms only.')
            stream_filter.scope = 'INTERNAL'
            stream_filter.privacy = 'PRIVATE'
            
        #We should be able to modify external rooms history but, for now it is broken...
        if settings.view_history is not None:
            log.info('History can only be enabled for internal rooms. Changing scope to internal only.')
            stream_filter.scope = 'INTERNAL'
    
    stream_filter.stream_types = [V2AdminStreamType(type='ROOM')]

    return stream_filter

#Handle unknown arguments.
def handle_arg_errors(err, mode):
    log.error('{} for mode {}'.format(str(err), mode))
    exit()


#Methods that are called after parsing command line arguments.        
async def update_single_room(stream_id, settings):
    async with SymphonyBdk(get_bdk_config()) as bdk:
        sym_room_modifier = await SymphonyRoomModifier.create(bdk)
        log.info('BDK Created for {} with username {}'.format(sym_room_modifier.bot_info.id, sym_room_modifier.bot_info.username))
        log.info('[{}] Updating Single Stream with settings: {}'.format(stream_id, string_to_one_line(settings)))
        try:    
            result = await sym_room_modifier.update_room(stream_id, settings)
            log.info('[{}] Updated stream. New settings: {}'.format(stream_id, string_to_one_line(settings)))
            return result
        except:
            log.error('[{}] There was an error updating the stream.'.format(stream_id))
            
async def update_all_rooms(filter:V2AdminStreamFilter, settings):
    async with SymphonyBdk(get_bdk_config()) as bdk:
        try:
            sym_room_modifier = await SymphonyRoomModifier.create(bdk)
            log.info('BDK Created for {} with username {}'.format(sym_room_modifier.bot_info.id, sym_room_modifier.bot_info.username))
            log.info('Filtering streams using {}'.format(string_to_one_line(filter)))
            log.info('Updating all Streams with settings: {}'.format(string_to_one_line(settings)))  
            await sym_room_modifier.update_rooms_by_filter(filter, settings)
        except Exception as err:
            logging.exception('There was an error updating the streams.'.format(err))
        



#Helper functions
#Get Output File. Return default value if None
def get_output_file_path(output_flag):
    output_file = Path(output_flag)
    if output_file.is_dir():
        output_file = Path.joinpath(output_file,'{}-{}.csv'.format('output',datetime.now().strftime('%d%b%Y_%H-%M-%S')))
    log.info('Setting output to : {}'.format(output_file.absolute()))
    return output_file.absolute()

#Get Input File. Return default value if None
def get_input_file_path(input_flag):
    input_file = Path(input_flag)
    if input_file.is_dir():
        input_file = Path.joinpath(input_file, 'input.csv')
    log.info('Setting input to : {}'.format(input_file.absolute()))
    if input_file.exists():
        return input_file.absolute()
    else:
        log.error("Input file does not exist. Exiting...")
        exit()

#Initialize all available filter flags to None
def initialize_filter_flags():
    filter_flags = {}
    for flag in ALL_AVAILABLE_FILTER_ROOM_FLAGS:
        filter_flags[flag] = None
    return filter_flags

#Convert boolean command line arguments to python booleans.
def parse_bool(bool_str):
    upper_arg = str(bool_str).strip().upper()
    if upper_arg in ('T', 'TRUE'):
        return True
    elif upper_arg in ('F','FALSE'):
        return False
    else:
        raise ValueError('Value must be true/false')

#Log multi-line objects into one line.
def string_to_one_line(string_in):
    return ''.join(str(string_in).split())

def configure_logging(logging_config_file=None):
    if logging_config_file == None:
        logging_config_file = Path.joinpath(Path(__file__).parent, 'logging.conf')
    if Path(logging_config_file).is_file():
        logging.config.fileConfig(logging_config_file, disable_existing_loggers=False)
        print('Setting logging configuration as per {}'.format(logging_config_file))
    else:
        print('Logging Configuration file does not exist... Setting logging to defaults...')
        print('Please see modify_rooms.log for foull logs')
        logging.getLogger().setLevel(logging.DEBUG)
        fh = logging.FileHandler('modify_rooms.log', encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        logging.getLogger().addHandler(fh)
        logging.getLogger().addHandler(ch)
    
def get_bdk_config(bdk_config_file=None):
    if bdk_config_file == None:
        bdk_config_file = Path.joinpath(Path(__file__).parent, 'config.yaml')
    return BdkConfigLoader.load_from_file(bdk_config_file)

#Parse what mode to run from command line arguments    
def command_line_run(argv):
    if not argv:
        print_help()
        exit()
    if argv[0] == 'csv':
        csv_mode(argv[1:])
    elif argv[0] == 'single':
        single_mode(argv[1:])
    elif argv[0] == 'all':
        all_mode(argv[1:])
    else:
        print_help()
        exit()

if __name__=='__main__':
    configure_logging()
    command_line_run(sys.argv[1:])
    
