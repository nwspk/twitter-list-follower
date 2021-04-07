from tweepy.models import User
from unittest.mock import patch
import app
import pytest


@pytest.mark.parametrize(
    "all_requests, user_requests, expected",
    [(0, 0, 2), (1000, 0, 0), (0, 400, 0), (1000, 400, 0)]
)
@patch('app.tweepy.API', autospec=True)
@patch('app._DB', autospec=True)
def test_get_people_to_follow(mock_db, mock_api, all_requests, user_requests, expected):
    followers = [User(), User()]
    mock_db.get_item.side_effect = [{'count': all_requests}, {'count': user_requests}]
    mock_api.list_members.return_value = followers
    assert app.get_people_to_follow(mock_api) == (followers, expected)
