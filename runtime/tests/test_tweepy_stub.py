import datetime

import pytest
import tweepy
from freezegun import freeze_time

from tests.utils.tweepy_stub import TweepyStub


class TestTwitterStub:
    def test_mock_twitter_api_raises_error_when_limit_reached(self, mocked_tweepy):
        api = mocked_tweepy
        for i in range(400):
            api.create_friendship(i)
        with pytest.raises(tweepy.RateLimitError):
            api.create_friendship('401')

    def test_multiple_users(self, mock_tweepy_factory):
        user_one_api = mock_tweepy_factory('0001')
        user_two_api = mock_tweepy_factory('0002')
        for api in (user_two_api, user_one_api):
            for i in range(400):
                api.create_friendship(str(i))
        assert api.app_count == 800
        with pytest.raises(tweepy.RateLimitError):
            user_one_api.create_friendship('401')
            user_two_api.create_friendship('401')

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