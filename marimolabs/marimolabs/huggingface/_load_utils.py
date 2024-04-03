from __future__ import annotations

import io
import math
import re
import warnings
from typing import Any, Callable

import httpx
import yaml
from huggingface_hub import InferenceClient


def get_tabular_examples(model_name: str) -> dict[str, list[float]]:
    readme = httpx.get(
        f"https://huggingface.co/{model_name}/resolve/main/README.md"
    )
    if readme.status_code != 200:
        warnings.warn(
            f"Cannot load examples from README for {model_name}", UserWarning
        )
        example_data = {}
    else:
        yaml_regex = re.search(
            "(?:^|[\r\n])---[\n\r]+([\\S\\s]*?)[\n\r]+---([\n\r]|$)",
            readme.text,
        )
        if yaml_regex is None:
            example_data = {}
        else:
            example_yaml = next(
                yaml.safe_load_all(readme.text[: yaml_regex.span()[-1]])
            )
            example_data = example_yaml.get("widget", {}).get(
                "structuredData", {}
            )
    if not example_data:
        raise ValueError(
            f"No example data found in README.md of {model_name} - Cannot build gradio demo. "
            "See the README.md here: https://huggingface.co/scikit-learn/tabular-playground/blob/main/README.md "
            "for a reference on how to provide example data to your model."
        )
    # replace nan with string NaN for inference Endpoints
    for data in example_data.values():
        for i, val in enumerate(data):
            if isinstance(val, float) and math.isnan(val):
                data[i] = "NaN"
    return example_data


def cols_to_rows(
    example_data: dict[str, list[float]],
) -> tuple[list[str], list[list[float]]]:
    headers = list(example_data.keys())
    n_rows = max(len(example_data[header] or []) for header in headers)
    data = []
    for row_index in range(n_rows):
        row_data = []
        for header in headers:
            col = example_data[header] or []
            if row_index >= len(col):
                row_data.append("NaN")
            else:
                row_data.append(col[row_index])
        data.append(row_data)
    return headers, data


def postprocess_label(scores: list[dict[str, str | float]]) -> dict:
    return {c["label"]: c["score"] for c in scores}


def postprocess_mask_tokens(scores: list[dict[str, str | float]]) -> dict:
    return {c["token_str"]: c["score"] for c in scores}


def postprocess_question_answering(answer: dict) -> tuple[str, dict]:
    return answer["answer"], {answer["answer"]: answer["score"]}


def postprocess_visual_question_answering(
    scores: list[dict[str, str | float]]
) -> dict:
    return {c["answer"]: c["score"] for c in scores}


def zero_shot_classification_wrapper(client: InferenceClient):
    def zero_shot_classification_inner(
        input: str, labels: str, multi_label: bool
    ):
        return client.zero_shot_classification(
            input, labels.split(","), multi_label=multi_label
        )

    return zero_shot_classification_inner


def sentence_similarity_wrapper(client: InferenceClient):
    def sentence_similarity_inner(input: str, sentences: str):
        return client.sentence_similarity(input, sentences.split("\n"))

    return sentence_similarity_inner


def text_generation_wrapper(client: InferenceClient):
    def text_generation_inner(input: str):
        return input + client.text_generation(input)

    return text_generation_inner


def format_ner_list(input_string: str, ner_groups: list[dict[str, str | int]]):
    if len(ner_groups) == 0:
        return [(input_string, None)]

    output = []
    end = 0
    prev_end = 0

    for group in ner_groups:
        entity, start, end = (
            group["entity_group"],
            group["start"],
            group["end"],
        )
        output.append((input_string[prev_end:start], None))
        output.append((input_string[start:end], entity))
        prev_end = end

    output.append((input_string[end:], None))
    return output


def file_contents_wrapper(fn: Callable[..., Any]):
    def file_contents_inner(v: Any):
        return (
            fn(v)
            if isinstance(v, (bytes, str, io.BytesIO))
            else fn(v.contents)  # type: ignore
        )

    return file_contents_inner


def token_classification_wrapper(client: InferenceClient):
    def token_classification_inner(input: str):
        ner_list = client.token_classification(input)
        return format_ner_list(input, ner_list)  # type: ignore

    return token_classification_inner


def tabular_wrapper(client: InferenceClient, pipeline: str):
    # This wrapper is needed to handle an issue in the InfereneClient where the model name is not
    # automatically loaded when using the tabular_classification and tabular_regression methods.
    # See: https://github.com/huggingface/huggingface_hub/issues/2015
    def tabular_inner(data):
        if pipeline not in ("tabular_classification", "tabular_regression"):
            raise TypeError(f"pipeline type {pipeline!r} not supported")
        assert client.model  # noqa: S101
        if pipeline == "tabular_classification":
            return client.tabular_classification(data, model=client.model)
        else:
            return client.tabular_regression(data, model=client.model)


def object_detection_wrapper(client: InferenceClient):
    def object_detection_inner(input: str):
        annotations = client.object_detection(input)
        formatted_annotations = [
            (
                (
                    a["box"]["xmin"],
                    a["box"]["ymin"],
                    a["box"]["xmax"],
                    a["box"]["ymax"],
                ),
                a["label"],
            )
            for a in annotations
        ]
        return (input, formatted_annotations)

    return object_detection_inner
