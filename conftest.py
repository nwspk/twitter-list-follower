from pytest import fixture


@fixture(scope='function')
def test_sqs_event():
    return {
        "Records": [
            {
                "messageId": "19dd0b57-b21e-4ac1-bd88-01bbb068cb78",
                "receiptHandle": "MessageReceiptHandle",
                "body": {
                    "user_id": "123",
                    "follower_id": "456"
                } ,
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": "1523232000000",
                    "SenderId": "123456789012",
                    "ApproximateFirstReceiveTimestamp": "1523232000001"
                },
                "messageAttributes": {},
                "md5OfBody": "{{{md5_of_body}}}",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:eu-west-2:123456789012:MyQueue",
                "awsRegion": "eu-west-2"
            }
        ]
    }
