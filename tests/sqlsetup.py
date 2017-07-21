# noinspection PyPackageRequirements
import pytest
from irisett.sql import DBConnection


DB_HOST = 'localhost'
DB_USERNAME = 'irisett_test'
DB_PASSWORD = 'Eichee0e'
DB_NAME = 'irisett_test'


@pytest.fixture(scope="module")
def initdb():
    pass


async def get_dbcon(reinit=False):
    dbcon = DBConnection(host=DB_HOST, user=DB_USERNAME, passwd=DB_PASSWORD, dbname=DB_NAME)
    await dbcon.initialize(only_init_tables=True, reset_db=reinit)
    return dbcon
