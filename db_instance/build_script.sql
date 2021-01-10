CREATE DATABASE esportsbot;

\c esportsbot

CREATE TABLE guild_info (
    guild_id bigint NOT NULL,
    log_channel_id bigint,
    default_role_id bigint
);

CREATE TABLE voicemaster_master (
    master_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL
);

ALTER TABLE voicemaster_master ALTER COLUMN master_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME voicemaster_master_master_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE voicemaster_slave (
    vc_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    owner_id bigint NOT NULL,
    locked boolean NOT NULL
);

ALTER TABLE voicemaster_slave ALTER COLUMN vc_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME voicemaster_vc_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

ALTER TABLE ONLY guild_info
    ADD CONSTRAINT loggingchannel_pkey PRIMARY KEY (guild_id);
	
ALTER TABLE ONLY voicemaster_master
    ADD CONSTRAINT voicemaster_master_pkey PRIMARY KEY (master_id);
	
ALTER TABLE ONLY voicemaster_slave
    ADD CONSTRAINT voicemaster_pkey PRIMARY KEY (vc_id);