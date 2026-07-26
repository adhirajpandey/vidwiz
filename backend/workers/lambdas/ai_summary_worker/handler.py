from aws_lambda_powertools.utilities.parser import envelopes, event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext

import summary_service
from vidwiz_worker.models import SummaryRequest

logger = summary_service.logger


@logger.inject_lambda_context(log_event=True)
@event_parser(model=SummaryRequest, envelope=envelopes.SqsEnvelope)
def lambda_handler(event: list[SummaryRequest], context: LambdaContext) -> None:
    del context
    return summary_service.process_batch(event)
