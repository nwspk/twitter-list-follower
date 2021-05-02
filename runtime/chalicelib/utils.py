import os
import boto3


sqs = boto3.resource('sqs')


def get_queue_url(queue_name: str):
    sqs_client = boto3.client("sqs")
    response = sqs_client.get_queue_url(
        QueueName=queue_name,
    )
    return response["QueueUrl"]


def queues() -> tuple[sqs.Queue, sqs.Queue, sqs.Queue]:
    return (
        sqs.Queue(get_queue_url(os.environ.get('APP_DO_NOW_QUEUE_NAME', ''))),
        sqs.Queue(get_queue_url(os.environ.get('APP_DO_LATER_QUEUE_NAME', ''))),
        sqs.Queue(get_queue_url(os.environ.get('APP_PROCESS_QUEUE_NAME', '')))
    )
