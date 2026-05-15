"""
Proxy helpers for Weixin publishing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from .config import WeixinConfig
from src.core.logger import logger


IP_CHECK_TIMEOUT = 8


class ProxyCheckError(RuntimeError):
    """Raised when the configured upload proxy is unsafe to use."""


def proxy_url() -> str:
    return WeixinConfig.proxy_url()


def requests_proxies(url: str | None = None) -> dict[str, str] | None:
    url = url or proxy_url()
    if not url:
        return None
    return {"http": url, "https": url}


def check_public_ip(use_proxy: bool = False) -> dict[str, Any]:
    url = proxy_url() if use_proxy else None
    proxies = requests_proxies(url)
    source = "proxy" if use_proxy else "direct"
    resp = requests.get(
        "http://ip-api.com/json/",
        params={
            "fields": "status,message,query,country,regionName,city,isp",
            "lang": "zh-CN",
        },
        proxies=proxies,
        timeout=IP_CHECK_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json() or {}
    if data.get("status") != "success":
        raise ProxyCheckError(data.get("message") or f"{source} IP lookup failed")

    return {
        "source": source,
        "ip": data.get("query") or "",
        "country": data.get("country") or "",
        "region": data.get("regionName") or "",
        "city": data.get("city") or "",
        "isp": data.get("isp") or "",
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def check_configured_proxy(strict_same_ip: bool = True) -> dict[str, Any]:
    if not WeixinConfig.PROXY_ENABLED:
        return {"enabled": False, "message": "proxy disabled"}

    url = proxy_url()
    if not url:
        raise ProxyCheckError("Weixin proxy is enabled but host or port is missing")

    proxy_info = check_public_ip(use_proxy=True)
    direct_info = None
    direct_error = None

    try:
        direct_info = check_public_ip(use_proxy=False)
    except Exception as exc:
        direct_error = str(exc)
        logger.warning(f"Direct IP lookup failed while checking proxy: {exc}")

    if (
        strict_same_ip
        and direct_info
        and proxy_info.get("ip")
        and proxy_info.get("ip") == direct_info.get("ip")
    ):
        raise ProxyCheckError(
            f"Proxy IP is the same as direct IP ({proxy_info['ip']}); refusing upload"
        )

    return {
        "enabled": True,
        "proxy_url": url,
        "proxy": proxy_info,
        "direct": direct_info,
        "direct_error": direct_error,
    }


def log_proxy_check_for_upload() -> dict[str, Any] | None:
    if not WeixinConfig.PROXY_ENABLED:
        return None

    result = check_configured_proxy(strict_same_ip=True)
    info = result.get("proxy") or {}
    location = " ".join(
        part for part in (info.get("country"), info.get("region"), info.get("city")) if part
    )
    logger.info(
        f"Weixin upload proxy ready: ip={info.get('ip') or '-'} location={location or '-'}"
    )
    return result
