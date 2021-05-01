import json
from tweepy.models import User
from unittest.mock import patch, MagicMock, create_autospec, call
import app as views
import pytest
from chalicelib.db import DynamoDBTwitterList
from chalice.test import Client
import boto3
from tweepy import RateLimitError
from moto import mock_sqs
import random


class TestIntegration:
    @mock_sqs
    @patch('app.tweepy.API.create_friendship')
    @patch('app.get_app_db')
    def test_empties_queue(self, mock_db, mock_friendship: MagicMock):
        mock_queue_resource = boto3.resource('sqs')
        mock_later_queue = mock_queue_resource.create_queue(QueueName='test-later-queue')
        for i in range(10):
            mock_later_queue.send_message(MessageBody=json.dumps({'user_id': '0000', 'follower_id': f'{i}'}))

        with patch('app.queues') as mock_queues:
            rate_error_index = random.randint(0, 9)
            mock_friendship.side_effect = [None if i < rate_error_index else RateLimitError(reason="Too many requests") for i in range(10)]
            mock_queues.return_value = [None, mock_later_queue]
            with Client(views.app) as client:
                event = client.events.generate_cw_event(
                    source='test.aws.events', detail_type='Scheduled Event', detail={}, resources=["arn:aws:events:us-east-1:123456789012:rule/MyScheduledRule"],
                    region='eu-west-test-1'
                )
            response = client.lambda_.invoke('process_later', event)
        mock_friendship.assert_has_calls([call(id=str(i)) for i in range(10)])
        assert int(mock_later_queue.attributes.get('ApproximateNumberOfMessagesDelayed')) == 10 - rate_error_index


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

