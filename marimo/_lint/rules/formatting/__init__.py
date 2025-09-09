from marimo._lint.rules.base import LintRule
from marimo._lint.rules.formatting.general import GeneralFormattingRule

FORMATTING_RULE_CODES : dict[str, type[LintRule]] = {
    "MF001": GeneralFormattingRule,
}

__all__ = ["GeneralFormattingRule", "FORMATTING_RULE_CODES"]
