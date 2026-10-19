from aws_lambda_powertools.utilities.parser import event_parser
from aws_lambda_powertools.utilities.parser.models import SqsModel
from aws_lambda_powertools.utilities.typing import LambdaContext

import summary_service
from vidwiz_worker.jobs import receive_count
from vidwiz_worker.models import SummaryRequest

logger = summary_service.logger


@logger.inject_lambda_context(log_event=False)
@event_parser(model=SqsModel)
def lambda_handler(event: SqsModel, context: LambdaContext) -> None:
    del context
    for record in event.Records:
        request = SummaryRequest.model_validate_json(record.body)
        summary_service.process_job(request.video_id, receive_count(record))
