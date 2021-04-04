import json
import os
import boto3
from chalice import Chalice, Response, Rate
from chalice.app import SQSEvent, SQSRecord, CloudWatchEvent
from typing import Union, Tuple
import tweepy
import sys

app = Chalice(app_name='cdk-list-follower')
app.debug = True
dynamodb = boto3.resource('dynamodb')
dynamodb_table = dynamodb.Table(os.environ.get('APP_TABLE_NAME', ''))
sqs = boto3.resource('sqs')
do_now_queue_name = sqs.Queue(os.environ.get('APP_DO_NOW_QUEUE_NAME', ''))

TWITTER_LIMIT = 1000
USER_LIMIT = 400


def get_queue_url(queue_name: str):
    sqs_client = boto3.client("sqs")
    response = sqs_client.get_queue_url(
        QueueName=queue_name,
    )
    return response["QueueUrl"]


def queues() -> Tuple[sqs.Queue, sqs.Queue]:
    return sqs.Queue(get_queue_url(os.environ.get('APP_DO_NOW_QUEUE_NAME', ''))), sqs.Queue(get_queue_url(os.environ.get('APP_DO_LATER_QUEUE_NAME', '')))


def tweepy_auth():
    return tweepy.OAuthHandler(
        os.environ.get('CONSUMER_KEY'), os.environ.get('CONSUMER_SECRET'), os.environ.get('CALLBACK_URL')
    )


@app.route('/')
def index():
    return {'hello': 'world'}


@app.route('/follow', methods=['POST', 'GET'])
def follow_the_list():
    """
    User has clicked a button to confirm they want to follow the list. We grab
    """
    sys.stdout.write(os.environ.get('CONSUMER_KEY'))
    auth = tweepy_auth()
    user_id = 'twitter-api'
    redirect_url = auth.get_authorization_url()
    _update_user(user_id, 'request_token', auth.request_token['oauth_token'])
    return Response(status_code=302, body='', headers={'Location': redirect_url})


@app.route('/redirect', methods=['GET'])
def redirect():
    """
    This view receives the redirect from the Twitter auth API. The request body will contain the authorisation tokens. From here, we call _get_people_to_follow
    to find, filter, and enqueue each request.
    """
    verifier = app.current_request.query_params.get('oauth_verifier')
    auth = tweepy_auth()
    token = _get_user_attribute('twitter-api', 'request_token')
    _update_user('twitter-api', 'request_token', '')
    auth.request_token = {'oauth_token': token,
                          'oauth_token_secret': verifier}

    auth.get_access_token(verifier)
    api = tweepy.API(auth)
    user_id = api.me().id_str
    _create_user(user_id)
    _update_user(user_id, 'access_token', auth.access_token)
    _update_user(user_id, 'access_token_secret', auth.access_token_secret)

    _get_people_to_follow(api)

    return {'redirected': 'here'}


def capacity(user_id: str, requests_to_process: int) -> bool:
    all_requests_today = _get_user_attribute('twitter-api', 'count')
    user_requests_today = _get_user_attribute(user_id, 'count')
    count_requests_to_make = requests_to_process
    return (user_requests_today + count_requests_to_make) <= 400 or (all_requests_today + count_requests_to_make) <= 1000


def _get_people_to_follow(twitter_api: tweepy.API):
    """
    This will access the Twitter API. It takes the Twitter list we'll be following and draws down the users in that list. It then filters out those that
    the user already follows, and then enqueues each request. If we've made 1,000 requests today, or 400 for this user, the request will have to be added to
    the 'do later' queue.
    """
    in_list = set(twitter_api.get_list(list_id='1358187814769287171'))
    # hard-coding the list for the data collective - change this or move to an environment variable if needed
    now_following = set(twitter_api.followers())
    to_follow = in_list.difference(now_following)
    all_requests_today = _get_user_attribute('twitter-api', 'count')
    user_requests_today = _get_user_attribute(twitter_api.me().id_str, 'count')
    count_requests_to_make = len(to_follow)
    if not capacity(twitter_api.me().id_str, count_requests_to_make):
        requests_to_process_now = 0
    else:
        requests_left_today = ((TWITTER_LIMIT - all_requests_today), (USER_LIMIT - user_requests_today), count_requests_to_make)
        requests_to_process_now = min(requests_left_today)
        _update_user('twitter-api', 'count', requests_to_process_now)
        _update_user(twitter_api.me().id_str, 'count', requests_to_process_now)
    for i, follower in enumerate(to_follow):
        message = json.dumps({'user_id': twitter_api.me().id_str, 'follower_id': follower.id_str})
        do_now_queue, do_later_queue = queues()
        if i >= requests_to_process_now:
            do_later_queue.send_message(MessageBody=message)
        else:
            do_now_queue.send_message(MessageBody=message)


@app.schedule(Rate(1, Rate.DAYS))
def process_later(event: CloudWatchEvent):
    """
    This function checks if there's capacity to do any following today. If there is, it polls the 'do_later_queue' to see if there's anything to process.
    If there is it processes the follows.
    """
    pass


@app.on_sqs_message(queue='do-now', batch_size=1)
def process_now(event: SQSEvent):
    """
    This function processes all items in the queue right now
    """
    for record in event:
        process_follow_from_record(record)


def process_follow_from_record(record: SQSRecord):
    """
    This function takes a person to follow and the requester's credentials and then touches the Twitter API to carry out this command. If the Twitter API
    responds with a 429, we've asked too many times, and will need to back off.
    """
    message_body = json.loads(record.body)
    user = _get_user(message_body['user_id'])
    auth = tweepy_auth()
    auth.set_access_token(user['access_token'], user['access_token_secret'])
    api = tweepy.API(auth)
    try:
        api.create_friendship(id=message_body['follower_id'])
    except tweepy.error.RateLimitError:
        do_later_queue = queues()[1]
        do_later_queue.send_message(json.dumps(message_body))


def _update_user(user_id: str, attribute: str, updated_value: Union[int, str]):
    dynamodb_table.update_item(
        Key={
            'user_id': user_id,
        },
        UpdateExpression=f'SET {attribute} = :val1',
        ExpressionAttributeValues={
            ':val1': updated_value
        }
    )
    return None


def _get_user_attribute(user_id: str, attribute='count'):
    try:
        item = _get_user(user_id)
    except KeyError:
        # user does not exist
        raise Exception
    return item[attribute]


def _get_user(user_id: str):
    response = dynamodb_table.get_item(
        Key={
            'user_id': user_id
        }
    )
    return response['Item']


def _create_user(user_id: str):
    dynamodb_table.put_item(
        Item={
            'user_id': user_id,
            'count': 0,
            'access_token': '',
            'access_token_secret': '',
        }
    )
    return None
