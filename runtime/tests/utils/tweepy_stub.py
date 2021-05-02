import time
from typing import Any
from unittest.mock import MagicMock, Mock

import tweepy


class TweepyStub(MagicMock):
    app_count = 0
    app_limit = 1000
    user_limit = 400

    def __init__(self, user: str, wait_period_seconds: float=86400.0):
        super().__init__(spec=tweepy.API)
        self.user = user
        self.friends = []
        self.count = 0
        self.locked_until = time.time()
        self.last_request = 0.0
        self.wait_period_seconds = wait_period_seconds

    def create_friendship(self, id: str):
        self.last_request = time.time()
        if self._locked_out():
            self._reset_counts()
            raise tweepy.RateLimitError(f"Rate limited until {self.locked_until}", api_code=429)
        elif not self._check_within_limit():
            self.locked_until += self.wait_period_seconds
            self._reset_counts()
            raise tweepy.RateLimitError(f"Too many requests. Locked until {self.locked_until}", api_code=429)
        else:
            self._update_counts()
            self.friends.append(id)
            return 0

    def _check_within_limit(self):
        return all(
                [
                    self.count < TweepyStub.user_limit,
                    TweepyStub.app_count < TweepyStub.app_limit
                ]
        )

    def _locked_out(self):
        """
        Determines if the user is currently rate limited for this time period. Resets every self.wait_period_seconds
        """
        return time.time() <= self.locked_until

    def _update_counts(self):
        self.count += 1
        TweepyStub.app_count += 1
        return None

    def _reset_counts(self):
        self.count = 0
        TweepyStub.app_count = 0
        return None

    def me(self):
        me = Mock
        me.id_str = self.user
        return me

    def _get_child_mock(self, **kw: Any) -> MagicMock:
        return MagicMock(**kw)
