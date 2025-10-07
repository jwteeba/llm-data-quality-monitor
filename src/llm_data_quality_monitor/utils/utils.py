import json
import os

import boto3
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import MetaData, Table, create_engine, select

load_dotenv()

AWS_SECRET = os.getenv("AWS_SECRET")
MYSQL_DB_NAME = os.getenv("MYSQL_DB_NAME")
MYSQL_HOST = os.getenv("MYSQL_HOST")


def get_db_credentials():
    """Get database credentials from AWS Secrets Manager"""
    client = boto3.client(
        "secretsmanager", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )
    response = client.get_secret_value(SecretId=AWS_SECRET)
    credentials = json.loads(response["SecretString"])
    return credentials["username"], credentials["password"]


def create_db_engine():
    """Create SQLAlchemy engine with optimized connection settings"""
    user = get_db_credentials()[0]
    password = get_db_credentials()[1]

    engine = create_engine(
        f"mysql+pymysql://{user}:{password}@{MYSQL_HOST}:3306/{MYSQL_DB_NAME}",
        connect_args={"connect_timeout": 30, "read_timeout": 30, "write_timeout": 30},
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    return engine


def read_data_from_mysql(table_name, engine):
    """Read data from MySQL database"""
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    with engine.connect() as conn:
        query = select(table)
        result = conn.execute(query)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    return df


def read_data_from_s3(bucket, key):
    """Read data from S3 bucket"""
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    df = pd.read_csv(obj["Body"])
    return df
