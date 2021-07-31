# twitter-list-follower

This is a little service to enable users to follow everyone in a list. Because of Twitter's API rate limits, a user's
request to follow an entire list is queued up behind everyone else using the service. Consequently it might be several
days before they see all the new people they're following.

If you use this software and enjoy it, consider buying the creator a coffee:
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/V7V24IODP)

## Setting up
If you'd like to set this up, you'll need a few things installed and a lot of patience. I'd recommend starting by
getting yourself into the runtime directory and setting up a virtual environment. Install the requirements.txt. I have a
TODO to fix up the requirements files so they can be separated out into what you need for dev versus production, because
at the moment they're too heavy.

Start off by running the tests - `pytest` - and check nothing's broken

## Architecture
Some might call the approach I've taken here "needlessly complex", to which I say "Probably". Deploying this infrastructure
into AWS results in the creation of a database, for keeping track of things, and three queues: a `process` queue, which
catches inputs from the frontend; a `do-now` queue, for when there's spare capacity in the twitter API; and a `do-later` queue,
for when there's not.

In the future I'd like to reduce this down to a single queue that sends messages to the back of itself and hides them for
some period of time if the twitter API says that this particular user has run out of quota, and stops processing for
some time if the application itself has run out of quota. I don't know how to do that quite yet. I'll get there though.

Probably
