# twitter-list-follower

This is a little service to enable users to follow everyone in a list. Because of Twitter's API rate limits, a user's request to follow an entire list is queued up behind everyone else using the service. Consequently it might be several days before you see all the new people you're following. 

If you use this software and enjoy it, consider buying the creator a coffee: [![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/V7V24IODP)

## What you'll need

- you'll need credentials for a Twitter app. Your users will be asked to authorise you, and you'll need quite significant permissions. You can get those by [following the instructions on the developer pages of Twitter.](https://developer.twitter.com/en/docs/getting-started). Those credentials go in [runtime/.chalice/config.json](./runtime/.chalice/example_config.json) - you will need to rename the `example_config.json` file to `config.json`
- you'll need [an AWS account, with some billing set up](https://aws.amazon.com/premiumsupport/knowledge-center/create-and-activate-aws-account/). Depending on how may users you have, this app could cost you a fortune - or it could cost you absolutely nothing. Lambda is complicated. I'm going to work on ways to call some of these asynchronously, rather than spamming queues, which is what it does at the moment.
- you'll need credentials for AWS stored locally. Check out the section of [this guide entitled 'Programmatic Access'](https://docs.aws.amazon.com/general/latest/gr/aws-sec-cred-types.html)

## How to deploy

You'll need to use the terminal. All of these instruction assume you're in the root directory (cdk-list-follower), which means if you type `ls` you should see this:
```
infrastructure  LICENSE   README.md requirements.txt  runtime
```
The first thing we're going to do is create a virtual environment to run our python code in:
`python3 -m venv venv`

your computer will think about it for a while.

once it's finished thinking, activate the virtual environment by typing `. venv/bin/activate` and install all the project's requirements by typing `pip install -r requirements.txt`. This will isntall everything in `runtime/requirements.txt` and `infrastructure/requirements.txt`

First things first - let's run the tests and make sure everything's set up correctly. Change directory to the runtime directory by typing `cd runtime` into your terminal. Then run the tests by typing `python -m pytest`

If these fail, then something has already gone wrong. Please raise an issue on this project with as much detail as possible, including what the computer spat back at you.

From the infrastructure folder - cdk-list-follower/infrastructure - type `cdk deploy` into your terminal
