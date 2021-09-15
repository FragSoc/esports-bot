import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import create_database, database_exists

from esportsbot.models import base

load_dotenv(dotenv_path=os.path.join("..", "secrets.env"))

db_string = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:5432/{os.getenv('POSTGRES_DB')}"

db = create_engine(db_string)

if not database_exists(db.url):
    create_database(db.url)

Session = sessionmaker(db)
session = Session()

base.metadata.create_all(db)

print("[DATABASE] - Models created")


class DBGatewayActions:
    """
    Base class for handling database queries
    """
    @staticmethod
    def list(db_model, **args):
        """
        Method to return a list of results that suit the model criteria

        Args:
            db_model (database_model): [The model to query in the database]
            **args (model_attributes): [The attributes specified for the query]

        Returns:
            [list]: [Returns a list of all models that fit the input models criteria]
        """
        try:
            query = session.query(db_model).filter_by(**args).all()
            return query
        except Exception as err:
            raise Exception(f"Error occurred when using list - {err}")

    @staticmethod
    def get(db_model, **args):
        """
        Method to return a record that suits the model criteria

        Args:
            db_model (database_model): [The model to query in the database]
            **args (model_attributes): [The attributes specified for the query]

        Returns:
            [list]: [Returns a list of all models that fit the input models criteria]
        """
        try:
            query = session.query(db_model).filter_by(**args).all()
            return query[0] if query != [] else query
        except Exception as err:
            raise Exception(f"Error occurred when using get - {err}")

    @staticmethod
    def update(model):
        """
        Method for updating a record in the database

        Args:
            model (database_model): [A class that contains the necessary information for an entry]
        """
        try:
            session.add(model)
            session.commit()
        except Exception as err:
            raise Exception(f"Error occurred when using update - {err}")

    @staticmethod
    def delete(model):
        """
        Method for deleting a record from the database

        Args:
            model (database_model): [A class that contains the necessary information for an entry]
        """
        try:
            session.delete(model)
            session.commit()
        except Exception as err:
            raise Exception(f"Error occurred when using delete - {err}")

    @staticmethod
    def create(model):
        """
        Method for adding a record to the database

        Args:
            model (database_model): [A class that contains the necessary information for an entry]
        """
        try:
            session.add(model)
            session.commit()
        except Exception as err:
            raise Exception(f"Error occurred when using create - {err}")
