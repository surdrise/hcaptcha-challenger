# -*- coding: utf-8 -*-
# Time       : 2023/8/19 18:04
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
import re
from hcaptcha_challenger.constant import BAD_CODE


def split_prompt_message(prompt_message: str, lang: str) -> str:
    """Detach label from challenge prompt"""
    if lang.startswith("zh"):
        if "中包含" in prompt_message or "上包含" in prompt_message:
            return re.split(r"击|(的每)", prompt_message)[2]
        if "的每" in prompt_message:
            return re.split(r"(包含)|(的每)", prompt_message)[3]
        if "包含" in prompt_message:
            return re.split(r"(包含)|(的图)", prompt_message)[3]
    elif lang.startswith("en"):
        prompt_message = prompt_message.replace(".", "").lower()
        if "containing" in prompt_message:
            th = re.split(r"containing", prompt_message)[-1][1:].strip()
            return th[2:].strip() if th.startswith("a") else th
        if prompt_message.startswith("please select all"):
            prompt_message = prompt_message.replace("please select all ", "").strip()
            return prompt_message
        if prompt_message.startswith("please click on the"):
            prompt_message = prompt_message.replace("please click on ", "").strip()
            return prompt_message
        if prompt_message.startswith("please click on all entities similar"):
            prompt_message = prompt_message.replace("please click on all entities ", "").strip()
            return prompt_message
        if prompt_message.startswith("please click on objects or entities"):
            prompt_message = prompt_message.replace("please click on objects or entities", "")
            return prompt_message.strip()
        if prompt_message.startswith("select all") and "images" not in prompt_message:
            return prompt_message.split("select all")[-1].strip()
        if "select all images of" in prompt_message:
            return prompt_message.split("select all images of")[-1].strip()
    return prompt_message


def label_cleaning(raw_label: str) -> str:
    """cleaning errors-unicode"""
    clean_label = raw_label
    for c in BAD_CODE:
        clean_label = clean_label.replace(c, BAD_CODE[c])
    return clean_label


def diagnose_task(words: str) -> str:
    """from challenge label to focus model name"""
    if not words or not isinstance(words, str) or len(words) < 2:
        raise TypeError(f"({words})TASK should be string type data")

    # Filename contains illegal characters
    inv = {"\\", "/", ":", "*", "?", "<", ">", "|"}
    if s := set(words) & inv:
        raise TypeError(f"({words})TASK contains invalid characters({s})")

    # Normalized separator
    rnv = {" ", ",", "-"}
    for s in rnv:
        words = words.replace(s, "_")

    for code, right_code in BAD_CODE.items():
        words.replace(code, right_code)

    words = words.strip()

    return words


def prompt2task(prompt: str, lang: str = "en") -> str:
    prompt = split_prompt_message(prompt, lang)
    prompt = label_cleaning(prompt)
    prompt = diagnose_task(prompt)
    return prompt


def handle(x):
    return split_prompt_message(label_cleaning(x), "en")
