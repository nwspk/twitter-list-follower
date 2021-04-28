import json
import os
import time
from chalice import Rate, Chalice
from chalice.app import SQSEvent, SQSRecord, CloudWatchEvent
from chalicelib.process_follow import ProcessFollow
from chalicelib.db import DynamoDBTwitterList
from typing import Tuple, List
import tweepy
from tweepy.models import User
from chalicelib.utils import queues
from chalicelib.api_blueprint import app as app_


app = Chalice(app_name='twitter-list-follower')
app.register_blueprint(app_)
app.debug = True

TWITTER_LIMIT = 1000
USER_LIMIT = 400

_DB = None


def get_app_db():
    global _DB
    if _DB is None:
        _DB = DynamoDBTwitterList.get_app_db()
    return _DB


def tweepy_auth():
    return ProcessFollow.tweepy_auth()


def reconstruct_twitter_api(user_id: str) -> tweepy.API:
    return ProcessFollow().reconstruct_twitter_api(user_id)


@app.on_sqs_message(queue='process', batch_size=1, name="enqueue_follows")
def enqueue_follows(event: SQSEvent):
    for record in event:
        user_id = record.body
        twitter_api = reconstruct_twitter_api(user_id)
        to_follow, requests_to_process_now = get_people_to_follow(twitter_api)
        for i, follower in enumerate(to_follow):
            message = json.dumps({'user_id': user_id, 'follower_id': follower.id_str})
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
    if int(os.environ.get('BLOCKED_UNTIL', 0.0)) > int(time.time()):
        pass
    else:
        db = DynamoDBTwitterList.get_app_db()
        db.reset_counts()
        do_later_queue = queues()[1]
        while True:
            message = do_later_queue.receive_message(VisibilityTimeout=1, MaxNumberOfMessages=10, WaitTimeSeconds=5)
            if message:
                process_now(message)
                # update the db here?
            else:
                break


@app.on_sqs_message(queue='do-now', batch_size=1)
def process_now(event: SQSEvent):
    """
    This function processes all items in the queue right now
    """
    do_later_queue = queues()[1]
    for record in event:
        if int(os.environ.get('BLOCKED_UNTIL', 0.0)) <= int(time.time()):
            # not blocked
            try:
                process_follow_from_record(record)
            except tweepy.TweepError as e:
                os.environ['BLOCKED_UNTIL'] = str(int(time.time()) + 86400)
                do_later_queue.send_message(record)
        else:
            do_later_queue.send_message(record)


def get_people_to_follow(twitter_api: tweepy.API) -> Tuple[List[User], int]:
    """
    This will access the Twitter API. It takes the Twitter list we'll be following and draws down the users in that list. It then filters out those that
    the user already follows, and then enqueues each request. If we've made 1,000 requests today, or 400 for this user, the request will have to be added to
    the 'do later' queue.
    """
    to_follow: List[User] = [
        member for member in tweepy.Cursor(twitter_api.list_members, list_id=os.environ.get('LIST_ID', '1358187814769287171')).items()
    ]
    # hard-coding the list for the data collective - change this or move to an environment variable if needed
    count_requests_to_make = len(to_follow)

    all_requests_today = get_app_db().get_item('twitter-api').get('count', 0)
    user_requests_today = get_app_db().get_item(twitter_api.me().id_str).get('count', 0)
    if user_requests_today >= 400 or all_requests_today >= 1000:
        requests_to_process_now = 0
    else:
        requests_left_today = ((TWITTER_LIMIT - all_requests_today), (USER_LIMIT - user_requests_today), count_requests_to_make)
        requests_to_process_now = min(requests_left_today)
        get_app_db().update_item('twitter-api', 'count', requests_to_process_now)
        get_app_db().update_item(twitter_api.me().id_str, 'count', requests_to_process_now)
    return to_follow, requests_to_process_now


def process_follow_from_record(record: SQSRecord):
    """
    This function takes a person to follow and the requester's credentials and then touches the Twitter API to carry out this command. If the Twitter API
    responds with a 429, we've asked too many times, and will need to back off.
    """
    message_body = json.loads(record.body)
    user = get_app_db().get_item(message_body['user_id'])
    auth = tweepy_auth()
    auth.set_access_token(user['access_token'], user['access_token_secret'])
    api = tweepy.API(auth)
    try:
        api.create_friendship(id=message_body['follower_id'])
    except tweepy.TweepError:
        do_later_queue = queues()[1]
        do_later_queue.send_message(json.dumps(message_body))
