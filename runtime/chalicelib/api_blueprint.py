import os
import sys
import tweepy
from chalice import Response, Blueprint
from .utils import queues
from .process_follow import ProcessFollow
from .db import DynamoDBTwitterList as db_

app = Blueprint(__name__)


@app.route('/')
def index():
    return {'hello': 'world'}


@app.route('/follow', methods=['POST', 'GET'])
def follow_the_list():
    """
    User has clicked a button to confirm they want to follow the list. We grab
    """
    sys.stdout.write(os.environ.get('CONSUMER_KEY'))
    auth = ProcessFollow.tweepy_auth()
    user_id = 'twitter-api'
    redirect_url = auth.get_authorization_url()
    db_.get_app_db().update_item(user_id, 'request_token', auth.request_token['oauth_token'])
    return Response(status_code=302, body='', headers={'Location': redirect_url})


@app.route('/redirect', methods=['GET'])
def redirect():
    """
    This view receives the redirect from the Twitter auth API. The request body will contain the authorisation tokens. From here, we call _get_people_to_follow
    to find, filter, and enqueue each request.
    """
    token = db_.get_app_db().get_item('twitter-api')['request_token']
    db_.get_app_db().update_item('twitter-api', 'request_token', '')

    verifier = app.current_request.query_params.get('oauth_verifier')
    auth = ProcessFollow.tweepy_auth()
    auth.request_token = {'oauth_token': token,
                          'oauth_token_secret': verifier}

    auth.get_access_token(verifier)
    api = tweepy.API(auth)
    user_id = api.me().id_str
    db_.get_app_db().add_item(user_id)
    db_.get_app_db().update_item(user_id, 'access_token', auth.access_token)
    db_.get_app_db().update_item(user_id, 'access_token_secret', auth.access_token_secret)

    process_queue = queues()[2]
    process_queue.send_message(MessageBody=user_id)

    # enqueue_follows(*get_people_to_follow(api), twitter_api=api)
    # this takes too long - needs to be queued

    return Response(status_code=302, body='', headers={'Location': f"https://www.twitter.com/lists/{os.environ.get('LIST_ID', '1358187814769287171')}"})
