import os
from typing import Union

import boto3


class TwitterListDB(object):
    def list_items(self):
        pass

    def add_item(self, user_id: str):
        pass

    def get_item(self, user_id) -> dict:
        pass

    def delete_item(self, uid):
        pass

    def update_item(self, user_id: str, attribute: str, updated_value: Union[int, str]):
        pass


class DynamoDBTwitterList(TwitterListDB):
    def __init__(self, table_resource):
        self._table = table_resource
        self.add_item("app")
        self.add_item("twitter-api")

    def add_item(self, user_id: str):
        self._table.put_item(
            Item={
                "user_id": user_id,
                "count": 0,
            }
        )
        return user_id

    def get_item(self, user_id: str):
        response = self._table.get_item(
            Key={
                "user_id": user_id,
            },
        )
        return response["Item"]

    def delete_item(self, user_id: str):
        self._table.delete_item(
            Key={
                "user_id": user_id,
            }
        )

    def update_item(self, user_id: str, attribute: str, updated_value: Union[int, str]):
        # We could also use update_item() with an UpdateExpression.
        item = self.get_item(user_id)
        item[attribute] = updated_value
        self._table.put_item(Item=item)

    def increase_count_by_one(self, user_id: str):
        item = self.get_item(user_id)
        item["count"] += 1
        self._table.put_item(Item=item)

    def reset_counts(self):
        response = self._table.scan()
        data = response["Items"]

        while "LastEvaluatedKey" in response:
            response = self._table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            data.extend(response["Items"])
        for datum in data:
            self.update_item(
                user_id=datum["user_id"], attribute="count", updated_value=0
            )

    @staticmethod
    def get_app_db():
        return DynamoDBTwitterList(
            boto3.resource("dynamodb").Table(os.environ["APP_TABLE_NAME"])
        )
