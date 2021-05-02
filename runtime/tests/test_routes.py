import json
import time
from tweepy.models import User
from unittest.mock import patch, MagicMock, create_autospec, call
import app as views
import pytest
from chalicelib.db import DynamoDBTwitterList
from chalice.test import Client
import boto3
from tweepy import RateLimitError
from moto import mock_sqs, mock_dynamodb
import random
import tweepy
from freezegun import freeze_time
import datetime
from conftest import TweepyStub


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
            rate_error_index = random.randint(1, 9)
            mock_friendship.side_effect = [None if i < rate_error_index else RateLimitError(reason="Too many requests") for i in range(10)]
            mock_queues.return_value = [None, mock_later_queue]
            with Client(views.app) as client:
                event = client.events.generate_cw_event(
                    source='test.aws.events', detail_type='Scheduled Event', detail={}, resources=["arn:aws:events:us-east-1:123456789012:rule/MyScheduledRule"],
                    region='eu-west-test-1'
                )
            response = client.lambda_.invoke('process_later', event)
        mock_db.return_value.increase_count_by_one.assert_has_calls([call('0000') for i in range(rate_error_index)], any_order=True)
        mock_friendship.assert_has_calls([call(id=str(i)) for i in range(10)])
        assert int(mock_later_queue.attributes.get('ApproximateNumberOfMessagesDelayed')) == 10 - rate_error_index

    @mock_sqs
    @mock_dynamodb
    @patch('app.get_app_db')
    def test_one_user(self, mock_db, mocked_tweepy):
        mocked_api = patch('app.reconstruct_twitter_api')
        mocked_api.return_value = mocked_tweepy
        assert False


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


class TestTwitterStub:
    def test_mock_twitter_api_raises_error_when_limit_reached(self, mocked_tweepy):
        api = mocked_tweepy
        for i in range(400):
            api.create_friendship(i)
        with pytest.raises(tweepy.RateLimitError):
            api.create_friendship('401')
        api._reset_counts()
        assert api.create_friendship('402') == 0

    def test_multiple_users(self, mock_tweepy_factory):
        user_one_api = mock_tweepy_factory('0001')
        user_two_api = mock_tweepy_factory('0002')
        for api in (user_two_api, user_one_api):
            for i in range(400):
                api.create_friendship(str(i))
        with pytest.raises(tweepy.RateLimitError):
            user_one_api.create_friendship('401')
            user_two_api.create_friendship('401')
        assert api.app_count == 800

    def test_time_out(self, mocked_tweepy):
        api = mocked_tweepy
        first_request_datetime = "2021-05-01 00:00:01"
        with freeze_time(first_request_datetime, auto_tick_seconds=5) as frozen_datetime:
            api.locked_until = datetime.datetime.strptime(first_request_datetime, "%Y-%m-%d %H:%M:%S").timestamp()
            api.count = 400
            TweepyStub.app_count = 400
            with pytest.raises(tweepy.RateLimitError):
                api.create_friendship('401')
            frozen_datetime.tick(datetime.timedelta(hours=24))
            response = api.create_friendship('401')
            assert response == 0
            assert api.app_count == 1
            assert api.count == 1

