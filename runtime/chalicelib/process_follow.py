import os
import boto3
from . import db
import tweepy


class ProcessFollow:
    def __init__(self):
        self.auth = self.tweepy_auth()

    @staticmethod
    def tweepy_auth():
        return tweepy.OAuthHandler(
            os.environ.get("CONSUMER_KEY"),
            os.environ.get("CONSUMER_SECRET"),
            os.environ.get("CALLBACK_URL"),
        )

    def reconstruct_twitter_api(self, user_credentials: dict) -> tweepy.API:
        auth = self.tweepy_auth()
        auth.set_access_token(
            user_credentials["access_token"], user_credentials["access_token_secret"]
        )
        return tweepy.API(auth)
