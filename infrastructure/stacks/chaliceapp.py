import os

from aws_cdk import (
    aws_dynamodb as dynamodb,
    core as cdk,
    aws_sqs as sqs
)
from chalice.cdk import Chalice


RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class ChaliceApp(cdk.Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.dynamodb_table = self._create_ddb_table()
        self.now_queue = self._create_sqs_queue('do-now')
        self.later_queue = self._create_sqs_queue('do-later')
        self.process_queue = self._create_sqs_queue('process')
        self.chalice = Chalice(
            self, 'ChaliceApp', source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                'environment_variables': {
                    'APP_TABLE_NAME': self.dynamodb_table.table_name,
                    'APP_DO_NOW_QUEUE_NAME': self.now_queue.queue_name,
                    'APP_DO_LATER_QUEUE_NAME': self.later_queue.queue_name,
                    'APP_PROCESS_QUEUE_NAME': self.process_queue.queue_name,
                }
            }
        )
        self.dynamodb_table.grant_read_write_data(
            self.chalice.get_role('DefaultRole')
        )
        for queue in (self.now_queue, self.later_queue):
            queue.grant_send_messages(
                self.chalice.get_role('DefaultRole')
            )
            queue.grant_consume_messages(
                self.chalice.get_role('DefaultRole')
            )

    def _create_ddb_table(self, name: str='AppTable'):
        dynamodb_table = dynamodb.Table(
            self, name,
            partition_key=dynamodb.Attribute(
                name='user_id', type=dynamodb.AttributeType.STRING),
            removal_policy=cdk.RemovalPolicy.DESTROY)
        cdk.CfnOutput(self, f'{name}Name',
                      value=dynamodb_table.table_name)
        return dynamodb_table

    def _create_sqs_queue(self, name: str='AppQueue'):
        queue = sqs.Queue(
            self, name, queue_name=name, visibility_timeout=cdk.Duration.seconds(60)
        )
        cdk.CfnOutput(self, f'{name}Name', value=queue.queue_name)
        return queue
