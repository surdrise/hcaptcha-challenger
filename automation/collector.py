# -*- coding: utf-8 -*-
# Time       : 2023/8/31 20:54
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
import asyncio
import os
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set

import httpx
from github import Auth, Github
from github.GitRelease import GitRelease
from github.GitReleaseAsset import GitReleaseAsset
from github.Issue import Issue
from loguru import logger
from playwright.async_api import BrowserContext as ASyncContext, async_playwright

from hcaptcha_challenger import AgentT, Malenia
from hcaptcha_challenger import split_prompt_message, diagnose_task
from hcaptcha_challenger.utils import SiteKey

PENDING_SITELINK = []

TEMPLATE_BINARY_DATASETS = """
> Automated deployment @ utc {now}

| Attributes | Details                      |
| ---------- | ---------------------------- |
| prompt     | {prompt}                     |
| type       | `{type}`                     |
| statistics | [#asset]({statistics})       |
| assets     | [{zip_name}]({download_url}) |

"""


@dataclass
class Gravitas:
    issue: Issue

    challenge_prompt: str = field(default=str)
    request_type: str = field(default=str)
    sitelink: str = field(default=str)
    mixed_label: str = field(default=str)
    """
    binary --> challenge_prompt
    area_select --> model_name
    """

    typed_dir: Path = None
    """
    init by collector
    ./automation/tmp_dir/image_label_binary/{mixed_label}/
    ./automation/tmp_dir/image_label_area_select/{question}/{mixed_label}
    """

    def __post_init__(self):
        body = [i for i in self.issue.body.split("\n") if i]
        self.challenge_prompt = body[2]
        self.request_type = body[4]
        self.sitelink = body[6]
        if "@" in self.issue.title:
            self.mixed_label = self.issue.title.split(" ")[1].strip()
        else:
            self.mixed_label = split_prompt_message(self.challenge_prompt, lang="en")

    @classmethod
    def from_issue(cls, issue: Issue):
        return cls(issue=issue)

    @property
    def zip_path(self) -> Path:
        label_diagnose_name = diagnose_task(self.typed_dir.name)
        now = datetime.strptime(str(datetime.now()), "%Y-%m-%d %H:%M:%S.%f").strftime("%Y%m%d%H%M")
        zip_path = self.typed_dir.parent.joinpath(f"{label_diagnose_name}.{now}.zip")
        return zip_path

    def zip(self):
        logger.info("pack datasets", mixed=self.zip_path.name)
        with zipfile.ZipFile(self.zip_path, "w") as zip_file:
            for root, dirs, files in os.walk(self.typed_dir):
                for file in files:
                    zip_file.write(os.path.join(root, file), file)

    def to_asset(self, archive_release: GitRelease) -> GitReleaseAsset:
        logger.info("upload datasets", mixed=self.zip_path.name)
        res = archive_release.upload_asset(path=str(self.zip_path))
        return res


def create_comment(asset: GitReleaseAsset, gravitas: Gravitas):
    body = TEMPLATE_BINARY_DATASETS.format(
        now=str(datetime.now()),
        prompt=gravitas.challenge_prompt,
        type=gravitas.request_type,
        zip_name=asset.name,
        download_url=asset.browser_download_url,
        statistics=asset.url,
    )
    comment = gravitas.issue.create_comment(body=body)
    logger.success(f"create comment", html_url=comment.html_url)


def load_gravitas_from_issues() -> List[Gravitas]:
    auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
    issue_repo = Github(auth=auth).get_repo("QIN2DIM/hcaptcha-challenger")
    binary_challenge_label = "🔥 challenge"

    tasks = []
    for issue in issue_repo.get_issues(
        labels=[binary_challenge_label],
        state="open",  # fixme `open`
        since=datetime.now() - timedelta(hours=24),  # fixme `24hours`
    ):
        if "Automated deployment @" not in issue.body:
            continue
        tasks.append(Gravitas.from_issue(issue))

    return tasks


def get_archive_release() -> GitRelease:
    auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
    archive_release = (
        Github(auth=auth)
        .get_repo("captcha-challenger/hcaptcha-whistleblower")
        .get_release(120534711)
    )
    return archive_release


# noinspection DuplicatedCode
@dataclass
class Collector:
    per_times: int = 3
    loop_times: int = 1
    tmp_dir: Path = Path(__file__).parent.joinpath("tmp_dir")

    pending_sitelink: List[str] = field(default_factory=list)
    pending_gravitas: List[Gravitas] = field(default_factory=list)

    typed_dirs: Set[Path] = field(default_factory=set)

    def __post_init__(self):
        cpt = os.getenv("COLLECTOR_PER_TIMES", "")
        self.per_times = int(cpt) if cpt.isdigit() else self.per_times
        logger.debug("init collector parameter", per_times=self.per_times)

        clt = os.getenv("COLLECTOR_LOOP_TIMES", "")
        self.loop_times = int(clt) if clt.isdigit() else self.loop_times
        logger.debug("init collector parameter", loop_times=self.loop_times)

        self.pending_sitelink.extend(PENDING_SITELINK)
        for skn in os.environ:
            if skn.startswith("SITEKEY_"):
                sk = os.environ[skn]
                logger.info("get sitekey from env", name=skn, sitekey=sk)
                self.pending_sitelink.append(SiteKey.as_sitelink(sk))

        if os.getenv("GITHUB_TOKEN"):
            self.pending_gravitas = load_gravitas_from_issues()
            for pi in self.pending_gravitas:
                self.pending_sitelink.append(pi.sitelink)
                logger.info("parse task from issues", prompt=pi.challenge_prompt)

        self.pending_sitelink = list(set(self.pending_sitelink))
        logger.info("create tasks", pending_sitelink=self.pending_sitelink)

    @logger.catch
    async def _collete_datasets(self, context: ASyncContext, sitelink: str):
        page = await context.new_page()
        agent = AgentT.from_page(page=page, tmp_dir=self.tmp_dir)

        await page.goto(sitelink)

        await agent.handle_checkbox()

        for pth in range(1, self.per_times + 1):
            try:
                label = await agent.collect()
            except (httpx.HTTPError, httpx.ConnectTimeout) as err:
                logger.warning(f"Collection speed is too fast", reason=err)
                await page.wait_for_timeout(500)
            except FileNotFoundError:
                pass
            except Exception as err:
                print(err)
            else:
                self.typed_dirs.add(agent.typed_dir)
                probe = list(agent.qr.requester_restricted_answer_set.keys())
                print(f">> COLLETE - progress=[{pth}/{self.per_times}] {label=} {probe=}")

            await page.wait_for_timeout(500)
            fl = page.frame_locator(agent.HOOK_CHALLENGE)
            await fl.locator("//div[@class='refresh button']").click()

    async def startup_collector(self):
        if not self.pending_sitelink:
            logger.info("No pending tasks, sentinel exits", tasks=self.pending_sitelink)
            return

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(locale="en-US")
            await Malenia.apply_stealth(context)
            for sitelink in self.pending_sitelink * self.loop_times:
                await self._collete_datasets(context, sitelink)
            await context.close()

    def post_datasets(self):
        if not self.pending_gravitas:
            return

        archive_release = get_archive_release()
        for gravitas in self.pending_gravitas:
            for typed_dir in self.typed_dirs:
                if gravitas.mixed_label not in typed_dir.name:
                    continue
                gravitas.typed_dir = typed_dir
                gravitas.zip()
                asset = gravitas.to_asset(archive_release)
                create_comment(asset, gravitas)

    async def bytedance(self):
        await self.startup_collector()
        self.post_datasets()


if __name__ == "__main__":
    collector = Collector()
    asyncio.run(collector.bytedance())
