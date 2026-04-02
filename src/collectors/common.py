from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from html import unescape
from typing import Dict
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) CodexTask1/1.0"


def fetch_text(url: str) -> str:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", "ignore")
    except Exception:
        result = subprocess.run(
            ["curl", "-L", "--max-time", "20", url],
            check=True,
            capture_output=True,
            text=False,
        )
        return result.stdout.decode("utf-8", "ignore")


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
