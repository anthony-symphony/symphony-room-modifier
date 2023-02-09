"""
Module that uses the SymphonyBdk to modify rooms. Allows users to modify a single stream, list of streams, all streams based on filters as well as CSV.
Also can export rooms to a CSV based on filter which can then be modified and used as the input.
Bdk provided must be for a bot with User Provisioning as it is required to list all streams, add and promote self for a room.
"""

__author__ = "Anthony Lee"
__maintainer__ = "Anthony Lee"
__email__ = "anthony.lee@symphony.com"

import logging
import json
import csv
import os

from typing import AsyncGenerator

from symphony.bdk.core.symphony_bdk import SymphonyBdk
from symphony.bdk.gen.pod_model.user_v2 import UserV2
from symphony.bdk.gen.pod_model.v2_admin_stream_filter import V2AdminStreamFilter
from symphony.bdk.gen.pod_model.v2_admin_stream_type import V2AdminStreamType
from symphony.bdk.gen.pod_model.v3_room_attributes import V3RoomAttributes
from symphony.bdk.gen.pod_model.v3_room_detail import V3RoomDetail
from symphony.bdk.gen.pod_model.v2_admin_stream_info import V2AdminStreamInfo

log = logging.getLogger("symphony_room_modifier")

#Known Error Message Reasons.
NOT_ROOM_MEMBER_MESSAGE = 'User {} is not a member of the room'
NOT_ROOM_OWNER_MESSAGE = 'Only room owners can perform this action.'
NOT_ABLE_TO_JOIN_MULTILATERAL_ROOMS = 'This person is not permitted to join multilateral rooms.'
NOT_ABLE_TO_DEMOTE_ONLY_OWNER = 'Unable to demote last owner of the chatroom.'
NOT_ABLE_TO_OWN_PUBLIC_ROOM ='User is not entitled to be a public room owner'

#Stream Type for only Rooms
STREAM_FILTER_TYPE_ROOM = V2AdminStreamType(type='ROOM')
#Stream Filter for all Rooms that are active and have internal origin.
STREAM_FILTER_INTERNAL_ORIGIN_ACTIVE = V2AdminStreamFilter(stream_types=[STREAM_FILTER_TYPE_ROOM], status='ACTIVE',origin='INTERNAL')

#Used to map CSV columns to Symphony Room Attributes
CSV_ROOM_TO_ROOM_ATTRIBUTES_MAP = {
    'name': {'mapped_key': 'name', 'type': 'string*'},
    'description': {'mapped_key':'description', 'type':'string'},
    'membersCanInvite': {'mapped_key':'members_can_invite', 'type':'bool'},
    'discoverable': {'mapped_key':'discoverable', 'type':'bool'},
    'copyProtected': {'mapped_key':'copy_protected', 'type':'bool+'},
    'viewHistory': {'mapped_key':'view_history', 'type':'bool'},
    'pinnedMessageId': {'mapped_key':'pinned_message_id', 'type':'string_b64'},
}

#Used to map modifiable and mandatory(streamId) Symphony room attributes to CSV columns
ROOM_TO_CSV_ROOM_MAP = {
    'id': {'mapped_key': 'streamId', 'is_system_info': True},
    'name': {'mapped_key': 'name', 'is_system_info': False},
    'description': {'mapped_key': 'description', 'is_system_info': False},
    'members_can_invite': {'mapped_key': 'membersCanInvite', 'is_system_info': False},
    'discoverable': {'mapped_key': 'discoverable', 'is_system_info': False},
    'copy_protected': {'mapped_key': 'copyProtected', 'is_system_info': False},
    'view_history': {'mapped_key': 'viewHistory', 'is_system_info': False},
    'pinned_message_id': {'mapped_key': 'pinnedMessageId', 'is_system_info': False},
}

#Used to map non-modifiable Symphony room attributes to CSV columns
ROOM_TO_CSV_ROOM_MAP_NON_MODIFIABLE = {
    'public': {'mapped_key': 'public', 'is_system_info': False},
    'read_only': {'mapped_key': 'readOnly', 'is_system_info': False},
    'cross_pod': {'mapped_key': 'crossPod', 'is_system_info': False},
    'multi_lateral_room': {'mapped_key': 'multiLateralRoom', 'is_system_info': False},
    'active': {'mapped_key': 'active', 'is_system_info': True},
    'keywords': {'mapped_key': 'keywords', 'is_system_info': False},
    'created_by_user_id': {'mapped_key': 'createdByUserId', 'is_system_info': True},
    'creation_date': {'mapped_key': 'creationDate', 'is_system_info': True}
}

#Take all mapped modifiable fields and put its CSV column name in a list. Used to specify what columns to export later on. 
CSV_STREAM_FIELD_NAMES = []
for key in ROOM_TO_CSV_ROOM_MAP:
    CSV_STREAM_FIELD_NAMES.append(ROOM_TO_CSV_ROOM_MAP[key]['mapped_key'])
    
#Take all mapped non-modifiable fields and put its CSV column name in a list. Appends (X) to the field name to mark that it is not modifiable.
CSV_STREAM_NON_MODIFIABLE_FIELD_NAMES = []
for key in ROOM_TO_CSV_ROOM_MAP_NON_MODIFIABLE:
    CSV_STREAM_NON_MODIFIABLE_FIELD_NAMES.append('{} (X)'.format(ROOM_TO_CSV_ROOM_MAP_NON_MODIFIABLE[key]['mapped_key']))

#Results only CSV fields.
CSV_RESULTS_STREAM_FIELD_NAMES = ['status', 'reason'] 
    
class SymphonyRoomModifier:
    """
    SymphonyRoomModifier object used to manipulate room settings.
    """
    def __init__(self, bdk:SymphonyBdk):
        """
        Do not use. Use SymphonyRoomModifier.create() instead.
        Args:
            bdk (SymphonyBdk): The Symphony BDK
        """
        self.bdk = bdk
        self.bot_info:UserV2

    @classmethod
    async def create(cls, bdk:SymphonyBdk):
        """
        Creates and initializes the SymphonyRoomModifier object which is used to manipulate room settings in Symphony.

        Args:
            bdk (SymphonyBdk): The SymphonyBdk

        Returns:
            SymphonyRoomModifier: Returns an initialized SymphonyRoomModifier.
        """
        log.debug('Creating SymphonyRoomModifier.')
        self = cls(bdk)
        self.bot_info = await bdk.sessions().get_session()
        log.info('SymphonyRoomModifier created for {} with with username {}'.format(self.bot_info.id, self.bot_info.username))
        return self

    async def get_rooms_by_filter(self, filter:V2AdminStreamFilter) -> AsyncGenerator[V2AdminStreamInfo, None] :
        """
        Get rooms by a specified V2AdminStreamFilter.

        Args:
            filter (V2AdminStreamFilter): The filter used to retrieve rooms with.

        Returns:
            AsyncGenerator[V2AdminStreamInfo, None]: List of streams retrieved.
        """
        log.debug("Retreiving list of streams")
        rooms = await self.bdk.streams().list_all_streams_admin(stream_filter=filter)
        log.info("Retrieved list of streams")
        return rooms
    
    async def get_room_info(self, stream_id:str) -> V3RoomDetail:
        """
        Get the room attributes for a specified stream Id.

        Args:
            stream_id (str): Stream Id to retrieve

        Returns:
            V3RoomDetail: The room attributes for the specified stream.
        """
        stream_id = _make_b64_id_safe(stream_id)
        log.debug('[{}] Getting room settings.'.format(stream_id))
        details = await self.bdk.streams().get_room_info(stream_id)
        log.info('[{}] Retreived room info.'.format(stream_id))
        log.debug('[{}] Room Info: {}'.format(stream_id, _string_to_one_line(details)))
        return details
    
    async def export_rooms_to_csv(self ,stream_filter:V2AdminStreamFilter, output_file:str , export_non_modifiable=False):
        """
        Exports rooms to a CSV file. Output can be modified and then used to update rooms using update_rooms_from_csv

        Args:
            stream_filter (V2AdminStreamFilter): The filter used to retrieve rooms
            output_file (str): The output path for the CSV file.
            export_non_modifiable (bool, optional): If set to true, it will also export non-modifiable settings. Defaults to False.

        Raises:
            err: Raises an exception when it is unable to export to CSV.
        """
        log.info('Exporting all rooms to CSV {} with filter: {}'.format(output_file, _string_to_one_line(stream_filter)))
        try:
            streams = await self.get_rooms_by_filter(stream_filter)
            with open(output_file, 'w', newline='', encoding='utf-8') as csv_file:
                field_names = CSV_STREAM_FIELD_NAMES
                if (export_non_modifiable):
                    field_names += CSV_STREAM_NON_MODIFIABLE_FIELD_NAMES
                csv_writer = csv.DictWriter(csv_file, fieldnames=field_names, extrasaction='ignore')
                csv_writer.writeheader()
                async for stream in streams:
                    log.debug('[{}] Writing Room to CSV.'.format(stream.id))
                    room = await self.get_room_info(stream.id)
                    csv_writer.writerow(_room_details_to_csv_dict(room, export_non_modifiable))
        except Exception as err:
            log.exception('There was an error exporting to CSV.')
            raise err
        log.info('Finished exporting all streams to {}'.format(output_file))
        
    async def update_rooms_from_csv(self, input_file:str, output_file:str=None, incoming_room_settings:V3RoomAttributes=None, export_non_modifiable = False, pre_check = True):
        """
        Updates the room based on a CSV file specified for input_file.

        Args:
            input_file (str): The input file path.
            output_file (str, optional): If specified it will output the results into a CSV file. Defaults to None.
            room_settings (V3RoomAttributes, optional): If specified it will use the room_settings instead of parsing from the CSV file. Defaults to None.
            export_non_modifiable (bool, optional): If set to true, it will also export non-modifiable settings. Defaults to False.
            pre_check (bool, optional): If true, it won't modify rooms if settings are unchanged.
        """
        log.info('Updating rooms from CSV file: {}'.format(input_file))
        if output_file:
            log.info('Exporting results to file: {}'.format(output_file))
        else:
            output_file = os.devnull # If not output file is specified, write everything to dev>null
        row = 0
        with open(input_file, 'r', encoding='utf-8') as rooms_csv, open(output_file, 'w', newline='', encoding='utf-8') as out_file:
            fields = CSV_STREAM_FIELD_NAMES
            if (export_non_modifiable):
                fields += CSV_STREAM_NON_MODIFIABLE_FIELD_NAMES
            fields += CSV_RESULTS_STREAM_FIELD_NAMES
            csv_writer = csv.DictWriter(out_file, fieldnames=fields, extrasaction='ignore')
            csv_writer.writeheader()
            for room in csv.DictReader(rooms_csv):
                row += 1
                log.info('Processing row {}'.format(row))
                try:
                    if 'streamId' in room:
                        room['streamId'] = _make_b64_id_safe(room['streamId'])
                        stream_id = _make_b64_id_safe(room['streamId'])
                        if incoming_room_settings is None:
                            log.debug("[{}] Parsing room attributes from CSV".format(stream_id))
                            room_settings = _csv_room_settings_to_v3_room_attributes(room)
                        else:
                            log.debug("[{}] Room attributes specified. Setting room attributes to specified attributes instead of CSV.".format(stream_id))
                            room_settings = incoming_room_settings
                        
                        should_update = True
                        current_room_info:V3RoomAttributes
                        if pre_check:
                            current_room_info = await self.get_room_info(stream_id)
                            should_update = _check_room_modified(current_room_info.room_attributes, room_settings)
                        if should_update:
                            log.info('[{}] Updating room from CSV with room attributes: {}'.format(stream_id, _string_to_one_line(room_settings)))
                            updated_room = await self.update_room(stream_id, room_settings)
                            result = _room_details_to_csv_dict(updated_room, export_non_modifiable)
                            result['status'] = 'SUCCESS'
                        else:
                            log.info('[{}] Current room settings match csv row... Skipping...'.format(stream_id))
                            result = _room_details_to_csv_dict(current_room_info, export_non_modifiable)
                            result['status'] = 'SKIPPED'
                            result['reason'] = 'Current room settings matched'
                        csv_writer.writerow(result)
                    else:
                        log.error('Row {} has no stream id specified... Skipping...'.format(row))
                except Exception as err:
                    reason = None
                    try:
                        reason = json.loads(err.body)
                        if ('message' in reason):
                            reason = reason['message']
                        else:
                            reason = str(err)
                    except:
                        reason = str(err)
                    if 'streamId' in room:
                        log.error('[{}] There was an error updating room on row {}: {}'.format(room['streamId'], row, reason))
                        result = room
                        result['status'] = 'FAILURE'
                        result['reason'] = reason
                        csv_writer.writerow(result)
                    else:
                        log.exception('Unknown exception occurred while updating room on row {}'.format(row))

    
    async def update_all_rooms(self, settings:V3RoomAttributes, pre_check = True) -> list[V3RoomDetail]:
        """
        Updates all rooms that are modifiable. This is defined by STREAM_FILTER_INTERNAL_ORIGIN_ACTIVE which is a filter for all Rooms that are active and have an internal origin.

        Args:
            settings (V3RoomAttributes): Settings you would like to modify all rooms to.

        Returns:
            list[V3RoomDetail]: Results of all the rooms modified.
        """
        log.info('Updating all room settings to: {}'.format(_string_to_one_line(settings)))
        return await self.update_rooms_by_filter(STREAM_FILTER_INTERNAL_ORIGIN_ACTIVE, settings, pre_check)
    
    async def update_rooms_by_filter(self, filter:V2AdminStreamFilter, settings:V3RoomAttributes, pre_check = True) -> list[V3RoomDetail]:
        """
        Update all rooms that match a filter with the settings specified. Modifies the incoming filter to only return active and internal rooms as those are the only rooms modifiable.
        To get around this, use update_rooms_by_filter_override.

        Args:
            filter (V2AdminStreamFilter): Filter to use to retrieve rooms.
            settings (V3RoomAttributes): Settings to update retrieved rooms.

        Returns:
            list[V3RoomDetail]: Results of all the rooms modified.
        """
        filter.stream_types=[STREAM_FILTER_TYPE_ROOM]
        filter.status = 'ACTIVE'
        filter.origin = 'INTERNAL'
        streams = await self.get_rooms_by_filter(filter)
        return await self.update_rooms(streams, settings, pre_check)
    
    async def update_rooms_by_filter_override(self, filter:V2AdminStreamFilter, settings:V3RoomAttributes, pre_check = True) -> list[V3RoomDetail]:
        """
        Used in case you want to attempt to modify any rooms that are not rooms, inactive or have external origin.
        However, these should fail as the only rooms modifable should be internal origin and active.

        Args:
            filter (V2AdminStreamFilter): Filter to use to retrieve rooms.
            settings (V3RoomAttributes): Settings to update retrieved rooms.

        Returns:
            list[V3RoomDetail]: Results of all the rooms modified.
        """
        streams = await self.get_rooms_by_filter(filter)
        return await self.update_rooms(streams, settings, pre_check)
    
    async def update_rooms(self, streams:list[V2AdminStreamInfo], settings:V3RoomAttributes, pre_check = True) -> list[V3RoomDetail]:
        """
        Update rooms from a list of V2AdminStreamInfo usually retreieved with get_rooms_by_filter
        
        Args:
            streams (list[V2AdminStreamInfo]): List of V2AdminStreamInfos retreieved by get_rooms_by_filter
            settings (V3RoomAttributes): Settings to update streams provided

        Returns:
            list[V3RoomDetail]: Results of all the rooms modified.
        """
        results = []
        async for stream in streams:
            try:
                stream_id = _make_b64_id_safe(stream.id)
                log.info('[{}] Updating Stream - {}'.format(stream_id, stream.attributes.room_name))
                updated_room = await self.update_room(stream_id, settings, pre_check)
                results.append(updated_room)
            except:
                log.error('[{}] There was an error updating room.'.format(stream_id))
        return results

    async def update_rooms_by_id(self, streams:list[str], settings:V3RoomAttributes, pre_check = True) -> list[V3RoomDetail]:
        """
        Update rooms from a list of stream ids

        Args:
            streams (list[str]): List of Stream Ids
            settings (V3RoomAttributes): Settings to update streams provided

        Returns:
            list[V3RoomDetail]: Results of all the rooms modified.
        """
        results = []
        async for stream in streams:
            try:
                stream_id = _make_b64_id_safe(stream)
                log.info('[{}] Updating Stream'.format(stream_id))
                updated_room = await self.update_room(stream_id, settings, pre_check)
                results.append(updated_room)
            except:
                log.error('[{}] There was an error updating room.'.format(stream_id))
        return results

    async def update_room(self, stream_id:str, settings:V3RoomAttributes, pre_check = True) -> V3RoomDetail:
        """
        Update room settings for a single stream

        Args:
            stream_id (str): Stream Id to modify
            settings (V3RoomAttributes): Settings to update stream with
            pre_check (bool): If True, will check old and new room settings before modifying.

        Returns:
            V3RoomDetail: Result of stream modified.
        """
        stream_id = _make_b64_id_safe(stream_id)
        try:
            if pre_check:
                current_room_info = await self.get_room_info(stream_id)
                if _check_room_modified(current_room_info.room_attributes, settings) is False:
                    log.info('[{}] Current room settings match... Skipping...'.format(stream_id))
                    return current_room_info
            log.debug('[{}] Calling update_room'.format(stream_id))
            updated_stream = await self.bdk.streams().update_room(stream_id, settings)
            log.info('[{}] Updated Stream - New Settings: {}'.format(stream_id, _string_to_one_line(updated_stream.room_attributes)))
            return updated_stream
        except Exception as err: #This will catch the exception where bot is not a room owner or is not in the room.
            reason = json.loads(err.body)
            if ('message' in reason and NOT_ROOM_OWNER_MESSAGE == reason['message']): #If the reason is due to not being an owner, make yourself the owner and try again.
                try:
                    log.debug('[{}] Bot is not owner. Attempting to make bot an owner.'.format(stream_id))
                    updated_stream = await self._promote_self_and_update_room(stream_id, settings)
                    await self._demote_self_for_room(stream_id) # Demote yourself afterwards to bring it back to original state.
                    return updated_stream
                except Exception as inner_err: #As both not being in the room and not being an owner throws the same message, this catches the error when you try to make yourself an owner.
                    try:
                        reason = json.loads(inner_err.body)
                        if ('message' in reason and (NOT_ROOM_MEMBER_MESSAGE.format(self.bot_info.id) == reason['message'])): #If the reason is due to yourself not being in the room add yourself to the room and then make yourself owner as well
                            try:
                                updated_stream = await self._add_self_and_update_room(stream_id, settings)
                                await self._remove_self_from_room(stream_id) # Remove yourself from room to bring back to original state.
                                return updated_stream
                            except:
                                self._update_room_exception_handler(stream_id, inner_err)
                        else:
                            self._update_room_exception_handler(stream_id, err)
                    except:
                        self._update_room_exception_handler(stream_id, err)
            else:
                self._update_room_exception_handler(stream_id, err)
 
 
    #Helper functions below. Do not use directly.
       
    def _update_room_exception_handler(self, stream_id:str, exception:Exception=None):
        #Exception handler while updating the room. If there is a reason, log the reason. If not re-raises the exception.
        reason = None
        try:
            reason = json.loads(exception.body)
            if ('message' in reason):
                reason = reason['message']
        except:
            log.exception('[{}] Unable to update room.'.format(stream_id))
        finally:
            log.error('[{}] Unable to update room. Reason: {}'.format(stream_id, reason))
            raise exception                

    async def _promote_self_and_update_room(self, stream_id:str, settings:V3RoomAttributes) -> V3RoomDetail:
        #Promote and retry updating the room again.
        await self._promote_self_to_owner(stream_id)
        return await self.update_room(stream_id, settings, False)
                
    async def _add_self_and_update_room(self, stream_id:str, settings:V3RoomAttributes) -> V3RoomDetail:
        #Add self to room, promote self to owner and then try updating the room again.
        log.debug('[{}] Bot is not a member.'.format(stream_id))
        await self._add_self_to_room(stream_id)
        await self._promote_self_to_owner(stream_id)
        return await self.update_room(stream_id, settings, False)
            
    async def _add_self_to_room(self, stream_id):
        #Add self to the room you want to modify. Catches any known reasons bot can't be added to the room. Re-raises any unknown exception.
        try:
            await self.bdk.streams().add_member_to_room(self.bot_info.id, stream_id)
            log.debug('[{}] Bot added to room.'.format(stream_id))
        except Exception as err:
            reason = json.loads(err.body)
            if ('message' in reason and (NOT_ABLE_TO_JOIN_MULTILATERAL_ROOMS == reason['message'])):
                log.error('[{}] Unable to join multilateral room. Please enable multilateral room entitlement for {}.'.format(stream_id, self.bot_info.id))
            else:
                raise err
        
    async def _promote_self_to_owner(self, stream_id):
        #Promote self to owner
        await self.bdk.streams().promote_user_to_room_owner(self.bot_info.id, stream_id)
        log.debug('[{}] Bot promoted to owner.'.format(stream_id))

        
    async def _remove_self_from_room(self, stream_id):
        #Remove self from room.
        await self.bdk.streams().remove_member_from_room(self.bot_info.id, stream_id)
        log.debug('[{}] Bot removed from room.'.format(stream_id))
        
    async def _demote_self_for_room(self, stream_id):
        #Demote self from owner. Catches any known reason bot can't be demoted. Re-raises any unknown exceptions.
        try:
            await self.bdk.streams().demote_owner_to_room_participant(self.bot_info.id, stream_id)
            log.debug('[{}] Bot demoted from owner.'.format(stream_id))
        except Exception as err:
            reason = json.loads(err.body)
            if ('message' in reason and (NOT_ABLE_TO_DEMOTE_ONLY_OWNER == reason['message'])):
                log.error('[{}] Unable to demote bot as it is the only owner.'.format(stream_id, self.bot_info.id))
            else:
                raise err

def _room_details_to_csv_dict(room:V3RoomDetail, export_non_modifiable=False) -> dict[str,str]:
    #Takes a V3RoomDetail object and makes it into a dictionary exportable to CSV. export_non_modifiable needs to be set to true to export non-modifiable fields
    
    room_settings={}
    room_attributes = room.room_attributes
    room_system_info = room.room_system_info
    
    for attribute in ROOM_TO_CSV_ROOM_MAP: #Map mandatory and modifiable fields
        mapped_key = ROOM_TO_CSV_ROOM_MAP[attribute]['mapped_key']
        value = None
        if attribute in room_system_info:
            value = room_system_info[attribute]
        elif attribute in room_attributes:
            value = room_attributes[attribute]
        if value is not None:
            if isinstance(value, bool):
                value = _bool_to_string(value)
                room_settings[mapped_key] = value
            else:
                room_settings[mapped_key] = value
        else:
            room_settings[mapped_key] = ''
    
    if export_non_modifiable:
        for attribute in ROOM_TO_CSV_ROOM_MAP_NON_MODIFIABLE: #Map non-modifiable fields. Only done if requested by export_non_modifiable
            mapped_key = ROOM_TO_CSV_ROOM_MAP_NON_MODIFIABLE[attribute]['mapped_key'] + ' (X)'
            value = None
            if attribute in room_system_info:
                value = room_system_info[attribute]
            elif attribute in room_attributes:
                value = room_attributes[attribute]
            if value is not None:
                if isinstance(value, bool):
                    value = _bool_to_string(value)
                    room_settings[mapped_key] = value
                else:
                    room_settings[mapped_key] = value
            else:
                room_settings[mapped_key] = ''
                
    return room_settings

#
def _csv_room_settings_to_v3_room_attributes(room_row):
    #Takes the CSV row and transforms it to a V3RoomAttributes object which will be used to modify a room.
    
    room_attributes = V3RoomAttributes()
    stream_id = _make_b64_id_safe(room_row['streamId'])
    for attribute in room_row:
        if attribute in CSV_ROOM_TO_ROOM_ATTRIBUTES_MAP:
            room_map = CSV_ROOM_TO_ROOM_ATTRIBUTES_MAP[attribute]
            attribute_name = room_map['mapped_key']
            attribute_type = room_map['type']
            val = room_row[attribute].strip()
            
            #Check for empty strings and set to None if empty so it will be ignored. If is "" set to empty string.
            if not val:
                val = None
            elif val == '""' or val == "''":
                val = ''
                
            # * type denotes it is required so if it was set to "" it will be ignored.
            if attribute_type.endswith('*') and val == '':
                logging.info('[{}] Attribute {} can not be empty. Ignoring...'.format(stream_id, attribute))
                val = None
            
            #Handle special cases
            if val is not None:          
                if attribute_type.startswith('bool'):
                    val = _string_to_bool(val)
                    #bool+ means boolean can only be set to True. If set to False, it will be ignored
                    if attribute_type.endswith('+'):
                        log.info("[{stream_id}] Attribute {attribute} set to {value}. {attribute} can only be set to true... Ignoring...".format(stream_id=stream_id, attribute=attribute, value=room_row[attribute]))
                        val = None
                #_b64_ denotes a string that needs to be encoded
                elif '_b64_' in attribute_type:
                    val = _make_b64_id_safe(val)
            
            if val is not None:
                room_attributes[attribute_name] = val

    return room_attributes

def _string_to_one_line(val) -> str:
    #Log multi-line objects into one line.
    return ''.join(str(val).split())

def _bool_to_string(val) -> str:
    #Transform boolean to a string for CSV output
    return str(val).lower() if isinstance(val, bool) else val

def _string_to_bool (val) -> bool:
    #Transform string in CSV input to a boolean
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return True
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return False
    else:
        raise None
    
def _make_b64_id_safe(id):
    #Convert Symphony Stream Ids to URL Safe ones if necessary
    return id.replace("+","-").replace("/","_").rstrip("=").rstrip()

def _check_room_modified(old_settings:V3RoomAttributes, new_settings:V3RoomAttributes):
    modified = False
    for attribute in ROOM_TO_CSV_ROOM_MAP:
        if attribute in new_settings and attribute in old_settings and new_settings[attribute] is not None and new_settings[attribute] != old_settings[attribute]:
            modified = True
            break
    return modified