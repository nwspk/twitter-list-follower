REST API backed by Amazon DynamoDB and SQS
==========================================

This template provides a REST API that's backed by an Amazon DynamoDB table and SQS queues.
This application is deployed using the AWS CDK.


Quickstart
----------

First, you'll need to install the AWS CDK if you haven't already. You'll also need some AWS credentials, and they'll need to be set up in your local environment.
The CDK requires Node.js and npm to run.
See the `Getting started with the AWS CDK
<https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html>`__ for
more details.

::

  $ npm install -g aws-cdk

Next you'll need to install the requirements for the project.

::

  $ pip install -r requirements.txt

There's also separate requirements files in the ``infrastructure``
and ``runtime`` directories if you'd prefer to have separate virtual
environments for your CDK and Chalice app.

To deploy the application, ``cd`` to the ``infrastructure`` directory.
If this is you're first time using the CDK you'll need to bootstrap
your environment.

::

  $ cdk bootstrap

Then you can deploy your application using the CDK.

::

  $ cdk deploy


Project layout
--------------

This project template combines a CDK application and a Chalice application.
These correspond to the ``infrastructure`` and ``runtime`` directory
respectively.  To run any CDK CLI commands, ensure you're in the
``infrastructure`` directory, and to run any Chalice CLI commands ensure
you're in the ``runtime`` directory.
