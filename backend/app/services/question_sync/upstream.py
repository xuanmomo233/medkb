"""Read-only adapter for the existing upstream question API."""
import asyncio
import base64
import json
import os
import re
import time

import httpx


class MissingQuestion(Exception):
    pass


class ExcludedQuestion(Exception):
    pass


def excluded(title):
    return bool(re.search(r"政治|肖秀荣|腿四|徐涛|毛中特|马原|思修|英语|田静|作文|阅读", title or ""))


class UpstreamError(Exception):
    pass


class AuthenticationRequired(UpstreamError):
    pass


def encode_token(token: str) -> str:
    # Same token protocol as server/wcyk_api.py; credentials stay in environment.
    from Crypto.Cipher import AES
    from Crypto.Hash import MD5

    salt, derived = os.urandom(8), b""
    while len(derived) < 48:
        derived += MD5.new((derived[-16:] if derived else b"") + b"ixunke" + salt).digest()
    stamp = int(time.time() * 1000)
    data = f"{token}#{stamp}".encode()
    padding = 16 - len(data) % 16
    encrypted = AES.new(derived[:32], AES.MODE_CBC, derived[32:48]).encrypt(data + bytes([padding]) * padding)
    text = base64.b64encode(b"Salted__" + salt + encrypted).decode() + f"#{stamp}"
    return base64.b64encode(text.encode()).decode()


def rows(envelope: dict, *, page: int, size: int):
    """Accept observed list/data wrappers, reject unknown shapes instead of skipping."""
    data = envelope.get("data")
    if isinstance(data, list):
        # Probe another page at the requested limit; repeated pages fail visibly.
        return data, len(data) >= size
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise UpstreamError("不支持的上游分页结构")
    if "total" not in data:
        raise UpstreamError("上游分页响应缺少 total，无法确认完整性")
    total = int(data["total"])
    if total < 0 or not data["data"] and page * size < total:
        raise UpstreamError("上游分页内容与总数不一致")
    return data["data"], page * size < total


class WcykClient:
    BASE = "https://api.ixunke.cn/xizongcangqiong"

    def __init__(self, token: str, *, client=None, delay=.15):
        if not token:
            raise ValueError("请配置 MEDKB_WCYK_TOKEN")
        self.token, self.delay = token, delay
        self.client = client or httpx.AsyncClient(timeout=30)
        self._banks, self._chapters, self._parents = {}, {}, {}

    async def close(self):
        await self.client.aclose()

    async def request(self, path, params=None, *, auth=True):
        for attempt in range(3):
            await asyncio.sleep(self.delay)
            query = dict(params or {})
            if auth:
                query.update(app="true", token=encode_token(self.token))
            try:
                response = await self.client.get(self.BASE + path, params=query, headers={
                    "User-Agent": "Mozilla/5.0 MicroMessenger/7.0.20 MiniProgramEnv/Windows",
                    "x-platform": "mp", "x-systemType": "android",
                })
                if response.status_code == 401:
                    raise AuthenticationRequired("上游登录会话已失效")
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, json.JSONDecodeError):
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise UpstreamError("上游网络或响应异常，未推进失败位置") from None
            if not isinstance(payload, dict):
                raise UpstreamError("不支持的上游响应")
            if payload.get("errno") == 100143:
                raise AuthenticationRequired("上游要求重新登录")
            # Unknown error codes can be auth/rate-limit errors, never assume a hole.
            if (payload.get("errno") == 1001 and payload.get("errmsg") == "题目不存在"
                    and path == "/api/question" and "id" in query):
                raise MissingQuestion()
            if payload.get("errno") != 0:
                raise UpstreamError("上游返回错误，需检查凭据或接口状态")
            return payload
        raise UpstreamError("上游重试耗尽")

    async def banks(self):
        page, seen = 1, set()
        while True:
            records, more = rows(await self.request("/api/q_bank", {"page": page, "pageSize": 500}, auth=False), page=page, size=500)
            ids = {str(record["id"]) for record in records}
            if ids & seen or more and not ids:
                raise UpstreamError("上游题库分页重复")
            seen.update(ids)
            for bank in records:
                self._banks[str(bank["id"])] = bank
                # Existing exclusion policy, restricted to non-medical exam banks.
                if not excluded(bank.get("title", "")):
                    yield bank
            if not more:
                return
            page += 1

    async def bank_chapters(self, bank):
        result = (await self.request("/api/chapter", {"qBankId": bank["id"]}, auth=False)).get("data")
        if not isinstance(result, list):
            raise UpstreamError("上游章节结构不受支持")
        def visit(items, prefix=""):
            for item in items:
                item = dict(item)
                item["full_title"] = " / ".join(x for x in (prefix, item.get("title", "")) if x)
                yield item
                yield from visit(item.get("children") or [], item["full_title"])
        chapters = list(visit(result))
        for chapter in chapters:
            self._chapters[(str(bank["id"]), str(chapter["id"]))] = chapter
        return chapters

    async def chapters(self):
        async for bank in self.banks():
            for chapter in await self.bank_chapters(bank):
                yield bank, chapter

    async def metadata(self, raw, bank=None, chapter=None):
        if not self._banks:
            async for _ in self.banks():
                pass
        if bank is None or str(bank["id"]) != str(raw.get("qBankId")):
            bank = self._banks.get(str(raw.get("qBankId")))
        if bank is None:
            raise UpstreamError("上游题库元数据缺失")
        if excluded(bank.get("title", "")):
            raise ExcludedQuestion()
        key = (str(bank["id"]), str(raw.get("chapterId")))
        if chapter is not None and str(chapter["id"]) != key[1]:
            chapter = None
        if chapter is None and key not in self._chapters:
            await self.bank_chapters(bank)
        chapter = chapter or self._chapters.get(key)
        if chapter is None:
            raise UpstreamError("上游章节元数据缺失")
        meta = dict(bank_id=str(bank["id"]), chapter_id=str(chapter["id"]), bank_title=bank.get("title", ""),
                    chapter_title=chapter.get("full_title", chapter.get("title", "")))
        if raw.get("parentId"):
            parent_key = str(raw["parentId"])
            if parent_key not in self._parents:
                try:
                    self._parents[parent_key] = (await self.request("/api/question", {"id": raw["parentId"]})).get("data")
                except MissingQuestion:
                    raise UpstreamError("材料题主干不存在，不能跳过子题") from None
            parent = self._parents[parent_key]
            if not isinstance(parent, dict) or not parent.get("stem"):
                raise UpstreamError("材料题主干缺失")
            meta["parent_stem"] = parent["stem"]
        return meta

    async def question(self, external_id):
        data = (await self.request("/api/question", {"id": external_id})).get("data")
        if data is None or data == []:
            raise UpstreamError("题目响应为空且没有明确缺号标记")
        data = data if isinstance(data, list) else [data]
        return [(raw, await self.metadata(raw)) for raw in data]

    async def chapter_page(self, bank, chapter, page):
        data, more = rows(await self.request("/api/question", {"chapterId": chapter["id"], "page": page, "pageSize": 200}), page=page, size=200)
        return [(raw, await self.metadata(raw, bank, chapter)) for raw in data], more
