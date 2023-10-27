# -*- coding: utf-8 -*-
# Time       : 2023/10/21 17:56
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
import json
from pathlib import Path
from typing import Tuple

import pytest

from hcaptcha_challenger import install
from hcaptcha_challenger import handle, ModelHub

install(upgrade=True)

modelhub = ModelHub.from_github_repo()
modelhub.parse_objects()

prompts = []

if (jp := Path(__file__).parent.joinpath("prompts.json")).exists():
    prompts = json.loads(jp.read_text(encoding="utf8"))


@pytest.mark.parametrize(
    "prompt2m", [("Please click on the head of the animal", "head_of_the_animal_2310_yolov8s.onnx")]
)
def test_lookup_model_by_ash(prompt2m: Tuple[str, str]):
    prompt, target = prompt2m
    handle(prompt)
    ash = f"{handle(prompt)} default"

    pending = []
    for focus_name, classes in modelhub.lookup_ash_of_war(ash):
        pending.append(focus_name)

    assert target in pending


@pytest.mark.parametrize("prompt", prompts)
def test_nested(prompt: str):
    if nested_models := modelhub.nested_categories.get(handle(prompt), []):
        for model_name in nested_models:
            if "yolo" in model_name:
                assert model_name in modelhub.ashes_of_war
                assert modelhub.ashes_of_war.get(model_name, [])
