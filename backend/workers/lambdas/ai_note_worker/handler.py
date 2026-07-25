from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import envelopes, event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext

from vidwiz_worker.config import WorkerSettings
from vidwiz_worker.models import Note
from vidwiz_worker.services import AiNoteService

logger = Logger()
service = AiNoteService(WorkerSettings.from_env(), logger)


@logger.inject_lambda_context(log_event=True)
@event_parser(model=Note, envelope=envelopes.SqsEnvelope)
def lambda_handler(event: list[Note], context: LambdaContext) -> None:
    del context
    return service.process_batch(event)
