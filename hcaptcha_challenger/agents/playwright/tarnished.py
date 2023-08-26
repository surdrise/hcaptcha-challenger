# -*- coding: utf-8 -*-
# Time       : 2023/8/25 13:59
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

from loguru import logger
from playwright.sync_api import BrowserContext as SyncContext, sync_playwright


class Tarnished:
    def __init__(
            self,
            user_data_dir: Path,
            *,
            record_dir: Path | None = None,
            record_har_path: Path | None = None,
            state_path: Path | None = None,
    ):
        self._user_data_dir = user_data_dir
        self._record_dir = record_dir
        self._record_har_path = record_har_path
        self.state_path = state_path

    @staticmethod
    def _apply_stealth(context: SyncContext):
        enabled_evasions = [
            "chrome.app",
            "chrome.csi",
            "chrome.loadTimes",
            "chrome.runtime",
            "iframe.contentWindow",
            "media.codecs",
            "navigator.hardwareConcurrency",
            "navigator.languages",
            "navigator.permissions",
            "navigator.plugins",
            "navigator.webdriver",
            "sourceurl",
            "webgl.vendor",
            "window.outerdimensions",
        ]

        for e in enabled_evasions:
            evasion_code = (
                Path(__file__)
                .parent.joinpath(f"puppeteer-extra-plugin-stealth/evasions/{e}/index.js")
                .read_text(encoding="utf8")
            )
            context.add_init_script(evasion_code)

        return context

    @staticmethod
    def _patch_cookies(context: SyncContext):
        five_days_ago = datetime.now() - timedelta(days=5)
        cookie = {
            "name": "OptanonAlertBoxClosed",
            "value": five_days_ago.isoformat(),
            "domain": ".epicgames.com",
            "path": "/",
        }
        context.add_cookies([cookie])

    def storage_state(self, context: SyncContext):
        if self.state_path:
            logger.info("Storage ctx_cookie", path=self.state_path)
            context.storage_state(path=self.state_path)

    def execute(
            self,
            sequence,
            *,
            parameters: Dict[str, Any] = None,
            headless: bool = False,
            locale: str = "en-US",
            **kwargs,
    ):
        with sync_playwright() as p:
            context = p.firefox.launch_persistent_context(
                user_data_dir=self._user_data_dir,
                headless=headless,
                locale=locale,
                record_video_dir=self._record_dir,
                record_har_path=self._record_har_path,
                args=["--hide-crash-restore-bubble"],
                **kwargs,
            )
            self._apply_stealth(context)
            self._patch_cookies(context)

            if not isinstance(sequence, list):
                sequence = [sequence]
            for container in sequence:
                logger.info("Execute task", name=container.__name__)
                kws = {}
                params = inspect.signature(container).parameters
                if parameters and isinstance(parameters, dict):
                    for name in params:
                        if name != "context" and name in parameters:
                            kws[name] = parameters[name]
                if not kws:
                    container(context)
                else:
                    container(context, **kws)
            context.close()
