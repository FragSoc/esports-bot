import logging
import os
from typing import Any

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import create_database, database_exists

from database.models import base

if os.getenv("DB_OVERRIDE"):
    DB_STRING = os.getenv("DB_OVERRIDE")
else:
    DB_STRING = f"postgresql://" \
                f"{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@" \
                f"{os.getenv('POSTGRES_HOST')}:5432/{os.getenv('POSTGRES_DB')}"

__all__ = ["DBSession"]


class __DBSession:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db = create_engine(DB_STRING)

        if not database_exists(self.db.url):
            create_database(self.db.url)

        __Session = sessionmaker(self.db)
        self.session = __Session()
        base.metadata.create_all(self.db)
        self.logger.info("Created DB models!")

    def list(self, table: Table, **args):
        """Get multiple values from a query in a given table.

        Args:
            table (Table): The table to query.

        Raises:
            Exception: If there was an error while accessing the DB.

        Returns:
            List: A list of rows from the table that match the paramters given.
        """
        try:
            return self.session.query(table).filter_by(**args).all()
        except Exception as error:
            self.logger.error(
                f"Encountered an exception while attempting to `list` {table.__class__.__name__} "
                f"using the following args - {args}"
            )
            raise Exception(f"Error occured when using DB list - {error}")

    def get(self, table: Table, **args):
        """Get a single row from a given Table.

        Args:
            table (Table): The table to query.

        Raises:
            Exception: If there was an error while accessing the DB.

        Returns:
            Any: A row matching the given query. Else None if no rows match the query.
        """
        try:
            query = self.session.query(table).filter_by(**args).all()
            return query[0] if query != [] else query
        except Exception as error:
            self.logger.error(
                f"Encountered an exception while attempting to `get` {table.__class__.__name__} "
                f"using the following args - {args}"
            )
            raise Exception(f"Error occured when using DB get - {error}")

    def delete(self, record: Any):
        """Delete a record in a Table.

        Args:
            record (Any): The record to delete.

        Raises:
            Exception: If there was an error while accessing the DB.
        """
        try:
            self.session.delete(record)
            self.session.commit()
        except Exception as error:
            self.logger.error(f"Encountered an exception while attempting to `delete` {record}")
            raise Exception(f"Error occured when using DB delete - {error}")

    def create(self, record: Any):
        """Create a new record in a given Table.

        Args:
            record (Any): The record to insert.

        Raises:
            Exception: If there was an error while accessing the DB.
        """
        try:
            self.session.add(record)
            self.session.commit()
        except Exception as error:
            self.logger.error(f"Encountered an exception while attempting to `create` {record}")
            raise Exception(f"Error occured when using DB create - {error}")

    def update(self, record: Any):
        """Update a given record with new data.

        Args:
            record (Any): The record to update with the changes made to it.

        Raises:
            Exception: If there was an error while accessing the DB.
        """
        try:
            self.session.add(record)
            self.session.commit()
        except Exception as error:
            self.logger.error(f"Encountered an exception while attempting to `update` {record}")
            raise Exception(f"Error occured when using DB update - {error}")


DBSession = __DBSession()
