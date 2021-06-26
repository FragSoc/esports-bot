from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from esportsbot.models import *
import os
from dotenv import load_dotenv

load_dotenv()

db_string = f"postgresql://{os.getenv('PG_USER')}:{os.getenv('PG_PWD')}@{os.getenv('PG_HOST')}:5432/{os.getenv('PG_DATABASE')}"

db = create_engine(db_string)

Session = sessionmaker(db)
session = Session()

base.metadata.create_all(db)

print("[DATABASE] - Models created")


class DBGatewayActions():
    """
    Base class for handling database queries
    """
    def list(self, db_model, **args):
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
            raise Exception(f"Error occured when using list - {err}")

    def get(self, db_model, **args):
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
            raise Exception(f"Error occured when using get - {err}")

    def update(self, model):
        """
        Method for updating a record in the database

        Args:
            model (database_model): [A class that contains the necessary information for an entry]
        """
        try:
            session.add(model)
            session.commit()
        except Exception as err:
            raise Exception(f"Error occured when using update - {err}")

    def delete(self, model):
        """
        Method for deleting a record from the database

        Args:
            model (database_model): [A class that contains the necessary information for an entry]
        """
        try:
            session.delete(model)
            session.commit()
        except Exception as err:
            raise Exception(f"Error occured when using delete - {err}")

    def create(self, model):
        """
        Method for adding a record to the database

        Args:
            model (database_model): [A class that contains the necessary information for an entry]
        """
        try:
            session.add(model)
            session.commit()
        except Exception as err:
            raise Exception(f"Error occured when using create - {err}")