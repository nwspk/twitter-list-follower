import datetime
import json
import random
from unittest.mock import patch, MagicMock, call

import pytest
from chalice.test import Client
from tweepy import RateLimitError, User

import app as views


class TestIntegration:

    @patch('app.tweepy.API.create_friendship')
    def test_if_tweepy_throws_error_messages_queued(self, mock_friendship: MagicMock, mock_sqs_resource, mock_db):
        mock_later_queue = mock_sqs_resource.create_queue(QueueName='test-later-queue')
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
        mock_friendship.assert_has_calls([call(id=str(i)) for i in range(rate_error_index)])
        assert int(mock_later_queue.attributes.get('ApproximateNumberOfMessagesDelayed')) == 10 - rate_error_index

    @pytest.mark.parametrize(
        ["people_to_follow", "expected_queue_values"],
        [
            [0, [0, 0]],
            [400, [0, 400]],
            [401, [1, 400]],
            [800, [400, 400]],
            [1000, [600, 400]],
            [1001, [601, 400]]
        ]
    )
    @patch('app.cursor', autospec=True)
    def test_integrated_enqueue_followers(self, mock_cursor, people_to_follow, expected_queue_values, mocked_tweepy, test_client, mock_sqs_resource,
                                          mock_db):

        stubbed_later_queue = mock_sqs_resource.create_queue(QueueName='test-later-queue')
        stubbed_now_queue = mock_sqs_resource.create_queue(QueueName='test-now-queue')

        mocked_queues = patch('app.queues', return_value=[stubbed_now_queue, stubbed_later_queue, None])

        mocked_api = patch('app.reconstruct_twitter_api', return_value=mocked_tweepy)

        to_follow = [User(api=mocked_api) for i in range(people_to_follow)]
        for i, u in enumerate(to_follow):
            u.id_str = i
        mock_cursor.return_value.items.return_value = to_follow
        with mocked_api, mocked_queues:
            test_client.lambda_.invoke(
                "enqueue_follows",
                test_client.events.generate_sqs_event(message_bodies=['0000'], queue_name='process')
            )
            assert stubbed_later_queue.attributes.get('ApproximateNumberOfMessages') == str(expected_queue_values[0])
            assert stubbed_now_queue.attributes.get('ApproximateNumberOfMessages') == str(expected_queue_values[1])

    @pytest.mark.parametrize(
        ["people_to_follow", "expected_queue_values", "locked_until"],
        [
            [0, 0, "2021-05-01 00:00:00"],
            [400, 0, "2021-05-01 00:00:00"],
            [401, 1, "2021-05-02 00:00:00"],
            [800, 400, "2021-05-02 00:00:00"],
            [1000, 600, "2021-05-02 00:00:00"],
            [1001, 601, "2021-05-02 00:00:00"]
        ]
    )
    def test_integrated_process_now(
            self, people_to_follow, expected_queue_values, locked_until, test_client, mock_db, mock_sqs_resource, mocked_tweepy, frozen_time
    ):
        stubbed_later_queue = mock_sqs_resource.create_queue(QueueName='test-later-queue')

        mocked_queues = patch('app.queues', return_value=[None, stubbed_later_queue, None])

        first_request_datetime = "2021-05-01 00:00:00"

        mocked_tweepy.locked_until = datetime.datetime.strptime(first_request_datetime, "%Y-%m-%d %H:%M:%S").timestamp()

        mocked_api = patch('app.tweepy.API', return_value=mocked_tweepy)

        with mocked_api, mocked_queues:
            test_client.lambda_.invoke(
                "process_now",
                test_client.events.generate_sqs_event(message_bodies=[json.dumps({'user_id': '0000', 'follower_id': i}) for i in range(people_to_follow)],
                                                      queue_name='do-now')
            )
        assert int(stubbed_later_queue.attributes.get('ApproximateNumberOfMessages')) + int(
            stubbed_later_queue.attributes.get('ApproximateNumberOfMessagesDelayed')) == expected_queue_values
        assert mocked_tweepy.locked_until == datetime.datetime.strptime(locked_until, "%Y-%m-%d %H:%M:%S").timestamp()

    @pytest.mark.parametrize(
        ["people_to_follow", "users"],
        [
            [0, ['0000']],
            [1, ['0000']],
            [400, ['0000']],
            [401, ['0000']],
            [800, ['0000']],
            [801, ['0000']]
        ]
    )
    def test_process_later_with_varying_queue_lengths(
            self, people_to_follow, users, mock_db, mocked_tweepy, mock_sqs_resource, test_client, mock_settings_env_vars, frozen_time):
        stubbed_later_queue = mock_sqs_resource.create_queue(QueueName='test-later-queue')
        messages = map(json.dumps, [{'user_id': '0000', 'follower_id': f'{i}'} for i in range(people_to_follow)])
        if people_to_follow < 10:
            for message in messages:
                stubbed_later_queue.send_message(MessageBody=message)
        else:
            entries = []
            for i, message in enumerate(messages, start=1):
                entries.append({'Id': str(i), 'MessageBody': json.dumps({'user_id': '0000', 'follower_id': f'{i}'})})
                if i % 10 == 0:
                    stubbed_later_queue.send_messages(Entries=entries)
                    entries.clear()
            if entries:
                stubbed_later_queue.send_messages(Entries=entries)

        mocked_queues = patch('app.queues', return_value=[None, stubbed_later_queue, None])

        mocked_api = patch('app.tweepy.API', return_value=mocked_tweepy)

        with mocked_api, mocked_queues, Client(views.app) as client:
            event = client.events.generate_cw_event(
                source='test.aws.events', detail_type='Scheduled Event', detail={},
                resources=["arn:aws:events:us-east-1:123456789012:rule/MyScheduledRule"],
                region='eu-west-test-1'
            )
            test_client.lambda_.invoke("process_later", event)
        if people_to_follow <= 400:
            assert views.get_app_db().get_item('app').get('count') == people_to_follow
            assert views.get_app_db().get_item(users[0]).get('count') == people_to_follow
        else:
            timed_out_until = datetime.datetime.strptime("2021-05-01 00:00:00", "%Y-%m-%d %H:%M:%S") + datetime.timedelta(hours=24)
            assert mocked_tweepy.locked_until == timed_out_until.timestamp()
            assert views.get_app_db().get_item('app').get('count') <= 1000
            for user in users:
                assert views.get_app_db().get_item(user).get('count') <= 400
