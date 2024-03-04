from dataclasses import dataclass


@dataclass
class AiCompletionRequest:
    prompt: str
    code: str
