import json
import os
from unittest.mock import patch

import boto3
import freezegun
from chalice.test import Client
from moto import mock_sqs, mock_dynamodb2
from pytest import fixture

from app import app
from tests.utils.tweepy_stub import TweepyStub


@fixture(autouse=True)
def mock_settings_env_vars():
    with patch.dict(
        os.environ,
        {
            "APP_TABLE_NAME": "TestAppTable",
            "APP_DO_NOW_QUEUE_NAME": "test-now-queue",
            "APP_DO_LATER_QUEUE_NAME": "test-later-queue",
            "APP_PROCESS_QUEUE_NAME": "test-process",
            "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_SECURITY_TOKEN": "testing",
            "AWS_SESSION_TOKEN": "testing",
            "AWS_DEFAULT_REGION": "us-east-1",
            "BLOCKED_UNTIL": "0.0",
        },
    ):
        yield


@fixture(scope="function")
def mock_sqs_resource(mock_settings_env_vars):
    with mock_sqs():
        yield boto3.resource("sqs", region_name="us-west-2")


@fixture(scope="function")
def mock_dynamo_resource(mock_settings_env_vars):
    with mock_dynamodb2():
        yield boto3.resource("dynamodb", region_name="us-west-2")


@fixture(scope="function")
def mock_db(mock_settings_env_vars, mock_dynamo_resource):
    from chalicelib.db import DynamoDBTwitterList

    test_table = mock_dynamo_resource.create_table(
        TableName="TestAppTable",
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
        ],
    )
    test_db = DynamoDBTwitterList(test_table)
    test_db.add_item("123")
    test_db.add_item("app")
    test_db.add_item("twitter-api")
    with patch("app.get_app_db", return_value=test_db):
        yield


@fixture(scope="function")
def test_client():
    with Client(app) as client:
        yield client


@fixture(scope="function")
def mocked_tweepy():
    yield TweepyStub("123")


@fixture(autouse=True)
def frozen_time():
    with freezegun.freeze_time("2021-05-01 00:00:00") as f:
        yield f


@fixture(scope="function")
def mock_tweepy_factory():
    def _tweepy_factory(user_id: str):
        return TweepyStub(user_id)

    yield _tweepy_factory


@fixture(scope="function")
def mock_message_body_sent_to_process_queue():
    package = {
        "access_token": "test-access-token",
        "access_token_secret": "test-access_token_secret",
        "user_id": "123",
        "list_id": "test-list-id",
    }
    return json.dumps(package)
