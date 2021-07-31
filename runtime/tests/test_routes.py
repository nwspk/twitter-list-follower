import json
from tweepy.models import User
from unittest.mock import patch, MagicMock, create_autospec, call
import app as views
import pytest
from chalicelib.db import DynamoDBTwitterList


class TestRoutes:
    @pytest.mark.parametrize(
        "all_requests, user_requests, expected",
        [(0, 0, 2), (1000, 0, 0), (0, 400, 0), (1000, 400, 0)],
    )
    @patch("app.tweepy.API", autospec=True)
    @patch("app.get_app_db")
    @patch("app.cursor", autospec=True)
    def test_get_people_to_follow(
        self, mock_cursor, patched_db, mocked_api, all_requests, user_requests, expected
    ):
        """
        This test checks whether 'get_people_to_follow' sorts requests into the right categories
        """
        followers = [User(), User()]
        mock_cursor.return_value.items.return_value = followers
        patched_db.return_value.get_item.side_effect = [
            {"count": all_requests},
            {"count": user_requests},
        ]
        assert views.get_people_to_follow(mocked_api, "test_id") == (
            followers,
            expected,
        )


@patch(
    "chalicelib.db.DynamoDBTwitterList.get_app_db",
    return_value=create_autospec(DynamoDBTwitterList),
)
@patch("app.get_people_to_follow")
@patch("app.queues")
class TestEnqueueFollowers:
    @pytest.mark.parametrize(
        ["requests_to_process_now", "expected_now", "expected_later"],
        [
            (
                2,
                [
                    {"user_id": "123", "follower_id": "0"},
                    {"user_id": "123", "follower_id": "1"},
                ],
                [],
            ),
            (
                0,
                [],
                [
                    {"user_id": "123", "follower_id": "0"},
                    {"user_id": "123", "follower_id": "1"},
                ],
            ),
            (
                1,
                [{"user_id": "123", "follower_id": "0"}],
                [{"user_id": "123", "follower_id": "1"}],
            ),
        ],
    )
    def test_enqueue_followers_with_default_list(
        self,
        mock_queues,
        mock_get_people_to_follow,
        mock_db,
        requests_to_process_now,
        expected_now,
        expected_later,
        test_client,
        mock_message_body_sent_to_process_queue,
    ):
        to_follow = [MagicMock(), MagicMock()]
        mock_later_queue = MagicMock()
        mock_now_queue = MagicMock()
        mock_queues.return_value = (mock_now_queue, mock_later_queue)

        for i, u in enumerate(to_follow):
            u.id_str = str(i)
        mock_get_people_to_follow.return_value = (to_follow, requests_to_process_now)
        test_client.lambda_.invoke(
            "enqueue_follows",
            test_client.events.generate_sqs_event(
                message_bodies=[mock_message_body_sent_to_process_queue],
                queue_name="process",
            ),
        )
        original_message = json.loads(mock_message_body_sent_to_process_queue)
        expected_messages_now = [
            call(MessageBody=message)
            for message in map(
                json.dumps,
                ({**original_message, **follower_id} for follower_id in expected_now),
            )
        ]
        expected_messages_later = [
            call(MessageBody=message)
            for message in map(
                json.dumps,
                ({**original_message, **follower_id} for follower_id in expected_later),
            )
        ]
        mock_now_queue.send_message.assert_has_calls(expected_messages_now)
        mock_later_queue.send_message.assert_has_calls(expected_messages_later)
