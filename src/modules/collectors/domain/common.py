from __future__ import annotations

import re
import subprocess
import threading
import time
from datetime import datetime
from html import unescape
from typing import Dict
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) CodexTask1/1.0"
DEFAULT_FETCH_RETRIES = 2
DEFAULT_BACKOFF_SECONDS = 1.0
DEFAULT_FETCH_TIMEOUT = 20
_THREAD_LOCAL = threading.local()


def get_http_session() -> requests.Session:
    session = getattr(_THREAD_LOCAL, "http_session", None)
    if session is None:
        session = requests.Session()
        session.trust_env = False
        adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
        )
        _THREAD_LOCAL.http_session = session
    return session


def fetch_text(url: str, retries: int = DEFAULT_FETCH_RETRIES) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = get_http_session().get(url, timeout=DEFAULT_FETCH_TIMEOUT)
            response.raise_for_status()
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except Exception as err:
            last_error = err
            try:
                result = subprocess.run(
                    [
                        "curl",
                        "-L",
                        "--noproxy",
                        "*",
                        "--max-time",
                        str(DEFAULT_FETCH_TIMEOUT),
                        "--retry",
                        "2",
                        "--retry-delay",
                        "1",
                        "--retry-all-errors",
                        "--http1.1",
                        "--compressed",
                        "-A",
                        USER_AGENT,
                        url,
                    ],
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
    response = get_http_session().post(
        url,
        data=payload,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=DEFAULT_FETCH_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


async def fetch_text_async(url: str, session: object | None = None) -> str:
    import aiohttp
    headers = {"User-Agent": USER_AGENT}
    if session is not None:
        async with session.get(url, headers=headers, timeout=DEFAULT_FETCH_TIMEOUT) as resp:
            return await resp.text(encoding="utf-8", errors="ignore")
    else:
        async with aiohttp.ClientSession(trust_env=False) as new_session:
            async with new_session.get(url, headers=headers, timeout=DEFAULT_FETCH_TIMEOUT) as resp:
                return await resp.text(encoding="utf-8", errors="ignore")


async def fetch_json_post_async(url: str, form_data: Dict[str, str], session: object | None = None) -> Dict[str, object]:
    import aiohttp
    from urllib.parse import urlencode
    
    payload = urlencode(form_data).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    if session is not None:
        async with session.post(url, data=payload, headers=headers, timeout=DEFAULT_FETCH_TIMEOUT) as resp:
            return await resp.json(content_type=None)
    else:
        async with aiohttp.ClientSession(trust_env=False) as new_session:
            async with new_session.post(url, data=payload, headers=headers, timeout=DEFAULT_FETCH_TIMEOUT) as resp:
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
