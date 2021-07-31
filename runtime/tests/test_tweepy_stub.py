import datetime

import pytest
import tweepy

from tests.utils.tweepy_stub import TweepyStub


class TestTwitterStub:
    def test_mock_twitter_api_raises_error_when_limit_reached(self, mocked_tweepy):
        api = mocked_tweepy
        for i in range(400):
            api.create_friendship(i)
        with pytest.raises(tweepy.RateLimitError):
            api.create_friendship("401")

    def test_multiple_users(self, mock_tweepy_factory):
        user_one_api = mock_tweepy_factory({"user_id": "0001"})
        user_two_api = mock_tweepy_factory({"user_id": "0002"})
        for api in (user_two_api, user_one_api):
            for i in range(400):
                api.create_friendship(str(i))
        assert api.app_count == 800
        with pytest.raises(tweepy.RateLimitError):
            user_one_api.create_friendship("401")
            user_two_api.create_friendship("401")

    def test_time_out(self, mocked_tweepy, frozen_time):
        api = mocked_tweepy
        api.count = 400
        TweepyStub.app_count = 400
        with pytest.raises(tweepy.RateLimitError):
            api.create_friendship("401")
        assert api.app_count == 0
        assert api.count == 0
        frozen_time.tick(datetime.timedelta(seconds=5))
        with pytest.raises(tweepy.RateLimitError):
            api.create_friendship("401")
        frozen_time.tick(datetime.timedelta(hours=24))
        response = api.create_friendship("401")
        assert response == 0
