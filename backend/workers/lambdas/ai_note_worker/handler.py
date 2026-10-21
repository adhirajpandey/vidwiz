from aws_lambda_powertools.utilities.parser import event_parser
from aws_lambda_powertools.utilities.parser.models import SqsModel
from aws_lambda_powertools.utilities.typing import LambdaContext

import note_service
from vidwiz_worker.jobs import receive_count
from vidwiz_worker.models import Moment

logger = note_service.logger


@logger.inject_lambda_context(log_event=False)
@event_parser(model=SqsModel)
def lambda_handler(event: SqsModel, context: LambdaContext) -> None:
    del context
    for record in event.Records:
        moment = Moment.model_validate_json(record.body)
        note_service.process_job(moment, receive_count(record))
