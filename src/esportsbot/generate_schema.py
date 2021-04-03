from .db_gateway import db_gateway


def generate_schema():
    # Does the esportsbot DB exist?
    esportsbot_exists = db_gateway().pure_return(
        "SELECT datname FROM pg_catalog.pg_database WHERE lower(datname) = lower('esportsbot')", "postgres")
    if not esportsbot_exists:
        # Esportsbot DB doesn't exist
        db_gateway().pure_query("CREATE DATABASE esportsbot", "postgres")

    # Does the guild_id table exist?
    guild_id_exists = db_gateway().pure_return(
        "SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'guild_info'")
    if not guild_id_exists:
        # Does not exist
        query_string = """
        CREATE TABLE guild_info(
            guild_id bigint NOT NULL,
            log_channel_id bigint,
            default_role_id bigint,
            num_running_polls int NOT NULL,
            role_ping_cooldown_seconds bigint NOT NULL
        );
        ALTER TABLE ONLY guild_info
        ADD CONSTRAINT loggingchannel_pkey PRIMARY KEY(guild_id);
        """
        db_gateway().pure_query(query_string)

    # Does the pingable_roles table exist?
    pingable_roles_exists = db_gateway().pure_return(
        "SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'pingable_roles'")
    if not pingable_roles_exists:
        # Does not exist
        query_string = """
        CREATE TABLE pingable_roles(
            role_id bigint NOT NULL,
            on_cooldown boolean NOT NULL,
            last_ping float NOT NULL,
            ping_count int NOT NULL,
            monthly_ping_count int NOT NULL,
            creator_id bigint NOT NULL,
            colour hex NOT NULL
        );
        ALTER TABLE ONLY pingable_roles
            ADD CONSTRAINT roleid_pkey PRIMARY KEY(role_id);
        """
        db_gateway().pure_query(query_string)

    # Does the guild_pingables table exist?
    guild_pingables_exists = db_gateway().pure_return(
        "SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'guild_pingables'")
    if not guild_pingables_exists:
        # Does not exist
        query_string = """
        CREATE TABLE guild_pingables(
            guild_id bigint NOT NULL,
            role_id bigint NOT NULL
        );
        ALTER TABLE ONLY guild_pingables
            ADD CONSTRAINT guildid_pkey FOREIGN KEY(guild_id) REFERENCES guild_info (guild_id);
        ALTER TABLE ONLY guild_pingables
            ADD CONSTRAINT roleid_pkey FOREIGN KEY(role_id) REFERENCES pingable_roles (role_id);
        """
        db_gateway().pure_query(query_string)

    # Does the reaction_menus table exist?
    reaction_menus_exists = db_gateway().pure_return(
        "SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'reaction_menus'")
    if not reaction_menus_exists:
        # Does not exist
        query_string = """
        CREATE TABLE reaction_menus(
            message_id bigint NOT NULL,
            menu jsonb
        );
        ALTER TABLE ONLY reaction_menus
            ADD CONSTRAINT menu_pkey PRIMARY KEY(message_id);
        """
        db_gateway().pure_query(query_string)

    # Does the voicemaster_master table exist?
    voicemaster_master_exists = db_gateway().pure_return(
        "SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'voicemaster_master'")
    if not voicemaster_master_exists:
        # Does not exist
        query_string = """
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
        """
        db_gateway().pure_query(query_string)

    # Does the voicemaster_slave table exist?
    voicemaster_slave_exists = db_gateway().pure_return(
        "SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'voicemaster_slave'")
    if not voicemaster_slave_exists:
        # Does not exist
        query_string = """
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
        """
        db_gateway().pure_query(query_string)

    # Does the twitch_info table exist?
    twitch_info_exists = db_gateway().pure_return(
        "SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'twitch_info'")
    if not twitch_info_exists:
        # Does not exist
        query_string = """
        CREATE TABLE public.twitch_info(
            id bigint NOT NULL,
            guild_id bigint NOT NULL,
            channel_id bigint NOT NULL,
            twitch_handle character varying NOT NULL,
            currently_live boolean NOT NULL,
            custom_message character varying
        );
        ALTER TABLE public.twitch_info ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY(
            SEQUENCE NAME public.twitch_info_id_seq
            START WITH 1
            INCREMENT BY 1
            NO MINVALUE
            NO MAXVALUE
            CACHE 1
        );
        ALTER TABLE ONLY public.twitch_info
        ADD CONSTRAINT twitch_info_pkey PRIMARY KEY(id);
        """
        db_gateway().pure_query(query_string)

    # Does the twitter_info table exist?
    twitter_info_exists = db_gateway().pure_return(
        "SELECT true::BOOLEAN FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = 'twitter_info'")
    if not twitter_info_exists:
        # Does not exist
        query_string = """
        CREATE TABLE public.twitter_info(
            id bigint NOT NULL,
            guild_id bigint NOT NULL,
            channel_id bigint NOT NULL,
            twitter_handle character varying NOT NULL,
            previous_tweet_id bigint NOT NULL
        );
        ALTER TABLE public.twitter_info ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY(
            SEQUENCE NAME public.twitter_info_id_seq
            START WITH 1
            INCREMENT BY 1
            NO MINVALUE
            NO MAXVALUE
            CACHE 1
        );
        ALTER TABLE ONLY public.twitter_info
        ADD CONSTRAINT twitter_info_pkey PRIMARY KEY(id);
        """
        db_gateway().pure_query(query_string)
