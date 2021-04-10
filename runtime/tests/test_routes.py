from tweepy.models import User
from unittest.mock import patch, MagicMock, create_autospec
import runtime.app as app
import pytest
from runtime.chalicelib.db import DynamoDBTwitterList


@pytest.mark.parametrize(
    "all_requests, user_requests, expected",
    [(0, 0, 2), (1000, 0, 0), (0, 400, 0), (1000, 400, 0)]
)
@patch('app.tweepy.Cursor', autospec=True)
@patch('app.tweepy.API', autospec=True)
@patch('runtime.app.get_app_db')
def test_get_people_to_follow(mock_db, mock_api, mock_cursor, all_requests, user_requests, expected):
    followers = [User(), User()]
    mock_dynamo = create_autospec(DynamoDBTwitterList)
    mock_db.return_value = mock_dynamo
    mock_cursor.return_value.items.return_value = followers
    mock_dynamo.get_item.side_effect = [{'count': all_requests}, {'count': user_requests}]
    assert app.get_people_to_follow(mock_api) == (followers, expected)
