from aws_lambda_powertools.utilities.parser import envelopes, event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext

import note_service
from vidwiz_worker.models import Note

logger = note_service.logger


@logger.inject_lambda_context(log_event=False)
@event_parser(model=Note, envelope=envelopes.SqsEnvelope)
def lambda_handler(event: list[Note], context: LambdaContext) -> None:
    del context
    return note_service.process_batch(event)
