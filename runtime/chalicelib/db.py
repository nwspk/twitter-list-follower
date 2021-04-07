from typing import Union


class TodoDB(object):
    def list_items(self):
        pass

    def add_item(self, user_id: str):
        pass

    def get_item(self, user_id):
        pass

    def delete_item(self, uid):
        pass

    def update_item(self, user_id: str, attribute: str, updated_value: Union[int, str]):
        pass


class DynamoDBTodo(TodoDB):
    def __init__(self, table_resource):
        self._table = table_resource

    def add_item(self, user_id: str):
        self._table.put_item(
            Item={
                'user_id': user_id,
                'count': 0,
                'access_token': '',
                'access_token_secret': '',
            }
        )
        return user_id

    def get_item(self, user_id: str):
        response = self._table.get_item(
            Key={
                'user_id': user_id,
            },
        )
        return response['Item']

    def delete_item(self, user_id: str):
        self._table.delete_item(
            Key={
                'user_id': user_id,
            }
        )

    def update_item(self, user_id: str, attribute: str, updated_value: Union[int, str]):
        # We could also use update_item() with an UpdateExpression.
        item = self.get_item(user_id)
        item[attribute] = updated_value
        self._table.put_item(Item=item)