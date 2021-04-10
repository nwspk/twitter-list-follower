from chalice import Chalice


def create_app():
    return Chalice(app_name='twitter-list-follower')
