import json
import os
import time
from typing import Tuple, List, Optional

import tweepy
from chalice import Rate, Chalice
from chalice.app import SQSEvent, CloudWatchEvent
from tweepy import Cursor as cursor
from tweepy.models import User

from chalicelib.db import DynamoDBTwitterList as db
from chalicelib.process_follow import ProcessFollow
from chalicelib.utils import queues, locked_out

app = Chalice(app_name="twitter-list-follower")
app.debug = True

TWITTER_LIMIT = 1000
USER_LIMIT = 400

_DB = None


def get_app_db():
    global _DB
    if _DB is None:
        _DB = db.get_app_db()
    return _DB


def tweepy_auth():
    return ProcessFollow.tweepy_auth()


def reconstruct_twitter_api(message_body: dict) -> tweepy.API:
    return ProcessFollow().reconstruct_twitter_api(message_body)


@app.on_sqs_message(queue="process", batch_size=1, name="enqueue_follows")
def enqueue_follows(event: SQSEvent):
    for record in event:
        message_body = dict(json.loads(record.body))
        twitter_api = reconstruct_twitter_api(message_body)
        to_follow, requests_to_process_now = get_people_to_follow(
            twitter_api, message_body["list_id"]
        )
        for i, follower in enumerate(to_follow):
            message = message_body.copy()
            message["follower_id"] = follower.id_str
            message = json.dumps(message)
            do_now_queue, do_later_queue = queues()[:2]
            if i >= requests_to_process_now:
                do_later_queue.send_message(MessageBody=message)
            else:
                do_now_queue.send_message(MessageBody=message)


@app.schedule(Rate(1, Rate.HOURS))
def process_later(event: CloudWatchEvent):
    """
    This function checks if there's capacity to do any following today. If there is, it polls the 'do_later_queue' to see if there's anything to process.
    If there is it processes the follows.
    """
    if locked_out():
        pass
    else:
        db = get_app_db()
        db.reset_counts()
        do_later_queue = queues()[1]
        while not locked_out():
            messages = do_later_queue.receive_messages(
                VisibilityTimeout=1, MaxNumberOfMessages=10
            )
            if not messages:
                break
            else:
                for message in messages:
                    process_follow_from_record(message)
                # update the db here?
    return 0


@app.on_sqs_message(queue="do-now", batch_size=1)
def process_now(event: SQSEvent):
    """
    This function processes all items in the queue right now
    """
    do_later_queue = queues()[1]
    for record in event:
        if not locked_out():
            # not blocked
            process_follow_from_record(record)
        else:
            do_later_queue.send_message(MessageBody=record.body)


def get_people_to_follow(
    twitter_api: tweepy.API, list_to_follow: Optional[str] = None
) -> Tuple[List[User], int]:
    """
    This will access the Twitter API. It takes the Twitter list we'll be following and draws down the users in that list.
    It then filters out those that the user already follows, and then enqueues each request. If we've made 1,000
    requests today, or 400 for this user, the request will have to be added to the 'do later' queue.
    """
    if list_to_follow is None:
        raise ValueError()
        # hard-coding the list for the data collective
    to_follow: List[User] = [
        member
        for member in cursor(twitter_api.list_members, list_id=list_to_follow).items()
    ]
    count_requests_to_make = len(to_follow)

    all_requests_today = get_app_db().get_item("twitter-api").get("count", 0)
    user_requests_today = get_app_db().get_item(twitter_api.me().id_str).get("count", 0)
    if user_requests_today >= USER_LIMIT or all_requests_today >= TWITTER_LIMIT:
        requests_to_process_now = 0
    else:
        requests_left_today = (
            (TWITTER_LIMIT - all_requests_today),
            (USER_LIMIT - user_requests_today),
            count_requests_to_make,
        )
        requests_to_process_now = min(requests_left_today)
        get_app_db().update_item("twitter-api", "count", requests_to_process_now)
        get_app_db().update_item(
            twitter_api.me().id_str, "count", requests_to_process_now
        )
    return to_follow, requests_to_process_now


def process_follow_from_record(message):
    """
    This function takes a person to follow and the requester's credentials and then touches the Twitter API to carry out this command. If the Twitter API
    responds with a 429, we've asked too many times, and will need to back off.
    When we upgrade to V2 of the API, we'll have to change some of the backing off
    """
    do_later_queue = queues()[1]
    if locked_out():
        do_later_queue.send_message(MessageBody=message.body, DelaySeconds=900)
    else:
        message_body = json.loads(message.body)
        auth = tweepy_auth()
        auth.set_access_token(
            message_body["access_token"], message_body["access_token_secret"]
        )
        api = tweepy.API(auth)
        try:
            api.create_friendship(id=message_body["follower_id"])
            get_app_db().increase_count_by_one(message_body["user_id"])
            get_app_db().increase_count_by_one("app")
        except tweepy.TweepError as e:
            do_later_queue.send_message(MessageBody=message.body, DelaySeconds=900)
            os.environ["BLOCKED_UNTIL"] = str(int(time.time()) + 86400)
