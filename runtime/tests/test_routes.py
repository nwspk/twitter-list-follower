import json
import os

from chalice.test import Client
from tweepy.models import User
from unittest.mock import patch, MagicMock, create_autospec, call
import app as views
import pytest
from chalicelib.db import DynamoDBTwitterList


@patch('app.tweepy.API', autospec=True)
class TestRoutes:

    @pytest.mark.parametrize(
        "all_requests, user_requests, expected",
        [(0, 0, 2), (1000, 0, 0), (0, 400, 0), (1000, 400, 0)]
    )
    @patch('app.get_app_db')
    @patch('app.tweepy.Cursor', autospec=True)
    def test_get_people_to_follow(self, mock_cursor, mock_db, mock_api, all_requests, user_requests, expected):
        followers = [User(), User()]
        mock_cursor.return_value.items.return_value = followers
        mock_db.return_value.get_item.side_effect = [{'count': all_requests}, {'count': user_requests}]
        assert views.get_people_to_follow(mock_api) == (followers, expected)

    @patch('chalicelib.db.DynamoDBTwitterList.get_app_db', return_value=create_autospec(DynamoDBTwitterList))
    @patch('app.get_people_to_follow')
    @patch('app.queues')
    @pytest.mark.parametrize(
        ["requests_to_process_now", "expected_now", "expected_later"],
        [
            (2, [{"user_id": "123", "follower_id": "0"}, {"user_id": "123", "follower_id": "1"}], []),
            (0, [], [{"user_id": "123", "follower_id": "0"}, {"user_id": "123", "follower_id": "1"}]),
            (1, [{"user_id": "123", "follower_id": "0"}], [{"user_id": "123", "follower_id": "1"}])
        ]
    )
    def test_enqueue_followers(self, mock_queues, mock_get_people_to_follow, mock_db, mock_api, requests_to_process_now, expected_now, expected_later, test_client):
        to_follow = [MagicMock(), MagicMock()]
        mock_later_queue = MagicMock()
        mock_now_queue = MagicMock()
        mock_queues.return_value = (mock_now_queue, mock_later_queue)

        for i, u in enumerate(to_follow):
            u.id_str = str(i)
        mock_get_people_to_follow.return_value = (to_follow, requests_to_process_now)
        body = "123"
        test_client.lambda_.invoke(
            "enqueue_follows",
            test_client.events.generate_sqs_event(message_bodies=[body], queue_name='process')
        )
        expected_messages_now = [call(MessageBody=message) for message in map(json.dumps, expected_now)]
        expected_messages_later = [call(MessageBody=message) for message in map(json.dumps, expected_later)]
        mock_now_queue.send_message.assert_has_calls(expected_messages_now)
        mock_later_queue.send_message.assert_has_calls(expected_messages_later)

