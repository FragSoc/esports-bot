from db_gateway import db_gateway

def get_cleaned_id(pre_clean_data):
    if str(pre_clean_data)[0] == '<':
        if str(pre_clean_data)[2] == '&':
            return int(str(pre_clean_data)[3:-1])
        else:
            return int(str(pre_clean_data)[2:-1])
    else:
        return int(pre_clean_data)

    
def get_whether_in_vm_master(guild_id, channel_id):
    in_master = db_gateway().get('voicemaster_master', params={'guild_id': guild_id, 'channel_id': channel_id})
    return bool(in_master)


def get_whether_in_vm_slave(guild_id, channel_id):
    in_slave = db_gateway().get('voicemaster_slave', params={'guild_id': guild_id, 'channel_id': channel_id})
    return bool(in_slave)


# def send_to_log_channel(guild_id):
#     db_logging_call = db_gateway().get('loggingchannel', params={'guild_id': guild_id})
#     return db_logging_call[0]['channel_id']