from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime
from html import unescape
from typing import Dict
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) CodexTask1/1.0"
DEFAULT_FETCH_RETRIES = 2
DEFAULT_BACKOFF_SECONDS = 1.0


def fetch_text(url: str, retries: int = DEFAULT_FETCH_RETRIES) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception as err:
            last_error = err
            try:
                result = subprocess.run(
                    ["curl", "-L", "--max-time", "20", url],
                    check=True,
                    capture_output=True,
                    text=False,
                )
                return result.stdout.decode("utf-8", "ignore")
            except Exception as curl_err:
                last_error = curl_err
                if attempt < retries:
                    # Exponential backoff to reduce transient timeout/network failures.
                    time.sleep(DEFAULT_BACKOFF_SECONDS * (2**attempt))
    assert last_error is not None
    raise last_error


def fetch_json_post(url: str, form_data: Dict[str, str]) -> Dict[str, object]:
    payload = urlencode(form_data).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


async def fetch_text_async(url: str, session: object | None = None) -> str:
    import aiohttp
    headers = {"User-Agent": USER_AGENT}
    if session is not None:
        async with session.get(url, headers=headers, timeout=20) as resp:
            return await resp.text(encoding="utf-8", errors="ignore")
    else:
        async with aiohttp.ClientSession() as new_session:
            async with new_session.get(url, headers=headers, timeout=20) as resp:
                return await resp.text(encoding="utf-8", errors="ignore")


async def fetch_json_post_async(url: str, form_data: Dict[str, str], session: object | None = None) -> Dict[str, object]:
    import aiohttp
    import json
    from urllib.parse import urlencode
    
    payload = urlencode(form_data).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    if session is not None:
        async with session.post(url, data=payload, headers=headers, timeout=20) as resp:
            return await resp.json(content_type=None)
    else:
        async with aiohttp.ClientSession() as new_session:
            async with new_session.post(url, data=payload, headers=headers, timeout=20) as resp:
                return await resp.json(content_type=None)


def strip_tags(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_datetime_or_now(value: str, fmt: str) -> str:
    try:
        return datetime.strptime(value, fmt).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
