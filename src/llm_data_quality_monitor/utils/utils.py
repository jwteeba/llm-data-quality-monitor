import json

import boto3
import pandas as pd
import streamlit as st
from sqlalchemy import MetaData, Table, create_engine, select

AWS_SECRET = st.secrets.aws_credentials.aws_secret_name
MYSQL_DB_NAME = st.secrets.aws_credentials.mysql_db_name
MYSQL_HOST = st.secrets.aws_credentials.mysql_host
AWS_ACCESS_KEY_ID = st.secrets.aws_credentials.aws_access_key_id
AWS_SECRET_ACCESS_KEY = st.secrets.aws_credentials.aws_secret_access_key
AWS_REGION = st.secrets.aws_credentials.aws_region


def get_db_credentials():
    """Get database credentials from AWS Secrets Manager"""
    client = boto3.client(
        "secretsmanager",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
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
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    obj = s3.get_object(Bucket=bucket, Key=key)
    df = pd.read_csv(obj["Body"])
    return df
