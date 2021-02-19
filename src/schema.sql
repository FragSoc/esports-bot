
IF NOT EXISTS(SELECT datname FROM pg_catalog.pg_database WHERE lower(datname) = lower('esportsbot'))
THEN
    CREATE DATABASE esportsbot;
END IF;

\c esportsbot

IF NOT EXISTS(SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'guild_info')
BEGIN
    CREATE TABLE guild_info (
        guild_id bigint NOT NULL,
        log_channel_id bigint,
        default_role_id bigint
    );
    ALTER TABLE ONLY guild_info
        ADD CONSTRAINT loggingchannel_pkey PRIMARY KEY (guild_id);

END

IF NOT EXISTS(SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'reaction_menus')
BEGIN
    CREATE TABLE reaction_menus (
        message_id bigint NOT NULL,
        menu JSONB
    );
    ALTER TABLE ONLY reaction_menus
        ADD CONSTRAINT menu_pkey PRIMARY KEY (message_id);

END

IF NOT EXISTS(SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'voicemaster_master')
BEGIN
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
    ALTER TABLE ONLY voicemaster_master
        ADD CONSTRAINT voicemaster_master_pkey PRIMARY KEY (master_id);
END

IF NOT EXISTS(SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'voicemaster_slave')
BEGIN
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
    ALTER TABLE ONLY voicemaster_slave
        ADD CONSTRAINT voicemaster_pkey PRIMARY KEY (vc_id);

END

