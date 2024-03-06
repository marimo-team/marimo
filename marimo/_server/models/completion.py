from dataclasses import dataclass


@dataclass
class AiCompletionRequest:
    prompt: str
    include_other_code: str
    code: str
