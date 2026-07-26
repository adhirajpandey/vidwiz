from dataclasses import dataclass
from pathlib import Path

INFRA_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = INFRA_DIR.parent
LAMBDA_DIR = REPOSITORY_DIR / "backend/workers/lambdas"


@dataclass(frozen=True)
class LambdaSpec:
    key: str
    construct_id: str
    function_name: str
    source: Path
    service_file: str


LAMBDA_SPECS = (
    LambdaSpec(
        key="transcript_dispatcher",
        construct_id="TranscriptDispatcher",
        function_name="vidwiz-prod-transcript-dispatcher",
        source=LAMBDA_DIR / "transcript_dispatcher",
        service_file="dispatch_service.py",
    ),
    LambdaSpec(
        key="ai_note_worker",
        construct_id="AiNoteWorker",
        function_name="vidwiz-prod-ai-note-worker",
        source=LAMBDA_DIR / "ai_note_worker",
        service_file="note_service.py",
    ),
    LambdaSpec(
        key="ai_summary_worker",
        construct_id="AiSummaryWorker",
        function_name="vidwiz-prod-ai-summary-worker",
        source=LAMBDA_DIR / "ai_summary_worker",
        service_file="summary_service.py",
    ),
)

LAMBDA_SPECS_BY_KEY = {spec.key: spec for spec in LAMBDA_SPECS}
