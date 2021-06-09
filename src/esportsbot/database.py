from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from esportsbot.models import *
import os

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
    def __init__(self):
        super().__init__()

    def list(self, model, **args):
        """
        Method to return a list of results that suit the model criteria

        Args:
            model (database_model): [A class that contains the necessary information for a query]

        Returns:
            [list]: [Returns a list of all models that fit the input models criteria]
        """
        reponse_list = session.query(model.guild_id).all()
        return reponse_list
        # reponse_list = []
        # mapper = inspect(model)
        # print(mapper)
        # result = session.query(mapper)
        # print(result)

    def read(self):
        return True

    def create(self, model):
        """
        Method for adding a record to the database

        Args:
            model (database_model): [A class that contains the necessary information for an entry]

        Returns:
            [Boolean]: [Returns true if successful, otherwise false]
        """
        try:
            session.add(model)
            session.commit()
            return True
        except:
            return False

    def update(self):
        return True

    def delete(self):
        return True