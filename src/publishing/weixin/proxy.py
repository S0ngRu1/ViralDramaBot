"""
视频号上传代理工具。

提供以下能力：
- `check_public_ip(use_proxy)`：通过多家公网 IP 查询服务（带 fallback）取出口 IP + 归属地。
- `check_configured_proxy(...)`：对当前代理配置做体检 —— 出口 IP / 直连 IP / 是否相同。
- `log_proxy_check_for_upload(...)`：上传前调用；带进程级 TTL 缓存，避免批量任务里反复打 ip-api.com 触发限流。
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Callable

import requests

from .config import WeixinConfig
from src.core.logger import logger


IP_CHECK_TIMEOUT = 8
# 代理出口 IP 在短时间内不会变化；批量上传时每个任务都重新检测会被 ip-api.com 限流（45 次/分钟），
# 同时大幅拉长批次耗时。这里做一个进程内 TTL 缓存，缓存 key 包含 (use_proxy, proxy_url)，
# 配置改了或开关切换都会自动失效。
PROXY_CHECK_TTL_SECONDS = 300


class ProxyCheckError(RuntimeError):
    """配置的代理不可用 / 不安全，调用方应拒绝上传。"""


def proxy_url() -> str:
    return WeixinConfig.proxy_url()


# ---------- 多源 IP 检测 ----------
# 每个 provider 是一个 (name, callable) — callable 接收 proxies 并返回标准化 dict 或抛异常。
# 顺序：ip-api.com（一次拿 IP+位置，最省事） → ifconfig.co（一次拿 IP+位置） → ipify+ipapi.co（兜底）。


def _provider_ip_api(session: requests.Session) -> dict[str, str]:
    resp = session.get(
        "http://ip-api.com/json/",
        params={
            "fields": "status,message,query,country,regionName,city,isp",
            "lang": "zh-CN",
        },
        timeout=IP_CHECK_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json() or {}
    if data.get("status") != "success":
        raise RuntimeError(data.get("message") or "ip-api.com lookup failed")
    return {
        "ip": data.get("query") or "",
        "country": data.get("country") or "",
        "region": data.get("regionName") or "",
        "city": data.get("city") or "",
        "isp": data.get("isp") or "",
    }


def _provider_ifconfig_co(session: requests.Session) -> dict[str, str]:
    resp = session.get(
        "https://ifconfig.co/json",
        timeout=IP_CHECK_TIMEOUT,
        headers={"User-Agent": "curl/8"},  # ifconfig.co 对非 curl UA 返回 HTML
    )
    resp.raise_for_status()
    data = resp.json() or {}
    if not data.get("ip"):
        raise RuntimeError("ifconfig.co returned no ip")
    return {
        "ip": data.get("ip") or "",
        "country": data.get("country") or "",
        "region": data.get("region_name") or "",
        "city": data.get("city") or "",
        "isp": data.get("asn_org") or "",
    }


def _provider_ipify_then_ipapi(session: requests.Session) -> dict[str, str]:
    """两段式：先用 ipify 拿 IP，再用 ipapi.co 解析地理位置。"""
    ip_resp = session.get(
        "https://api.ipify.org",
        params={"format": "json"},
        timeout=IP_CHECK_TIMEOUT,
    )
    ip_resp.raise_for_status()
    ip = (ip_resp.json() or {}).get("ip") or ""
    if not ip:
        raise RuntimeError("ipify returned no ip")
    info = {"ip": ip, "country": "", "region": "", "city": "", "isp": ""}
    # 位置查询最好也走同一通道（代理时验证代理出口）。失败时只丢位置信息，保留 IP。
    try:
        geo_resp = session.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=IP_CHECK_TIMEOUT,
        )
        geo_resp.raise_for_status()
        geo = geo_resp.json() or {}
        info.update(
            {
                "country": geo.get("country_name") or "",
                "region": geo.get("region") or "",
                "city": geo.get("city") or "",
                "isp": geo.get("org") or "",
            }
        )
    except Exception as e:
        logger.warning(f"ipapi.co 地理位置查询失败（保留 IP，地点留空）：{e}")
    return info


_PROVIDERS: list[tuple[str, Callable[[requests.Session], dict[str, str]]]] = [
    ("ip-api.com", _provider_ip_api),
    ("ifconfig.co", _provider_ifconfig_co),
    ("ipify+ipapi.co", _provider_ipify_then_ipapi),
]


def _build_session(use_proxy: bool, proxy_url_override: str | None = None) -> requests.Session:
    """
    构造单次 IP 检测用的 Session。

    关键：direct 分支必须 `trust_env=False`，否则 `requests` 会自动套用 Windows 系统代理 /
    `HTTP_PROXY` 环境变量。用户开了爱加速但同时启用了 Windows 系统代理时，"不传 proxies"
    其实仍会走系统代理 —— 导致 direct 出口 IP 和 proxy 出口 IP 完全相同，
    触发本不该出现的 "代理出口 IP 与直连 IP 相同" 误报。
    """
    session = requests.Session()
    if use_proxy:
        url = proxy_url_override or proxy_url()
        session.proxies.update({"http": url, "https": url})
        # proxy 分支也关掉 trust_env，避免 requests 把环境变量代理叠加上去；
        # 我们要的是「严格走配置的这个代理」，不要任何隐式叠加。
        session.trust_env = False
    else:
        session.trust_env = False
    return session


def _friendly_proxy_error(errors: list[str]) -> str:
    """
    把多源 IP 检测失败的原始堆栈文本归类成一句用户友好的中文短文案。

    存到数据库的 `last_check_error` / 返回给前端的 message 都用这里的输出 ——
    不让前端看到「HTTPConnectionPool(host=...) Max retries exceeded」这种没人能
    从里面读出可执行结论的内部细节。完整堆栈仍走 logger.warning 写到日志里，便于排查。
    """
    if not errors:
        return "代理检测失败"
    joined = " | ".join(errors).lower()
    if "read timed out" in joined or "readtimeouterror" in joined:
        return "代理响应超时（代理可能正在过载，请稍后重试或检查代理工具）"
    if "tunnel connection failed: 5" in joined:
        return "代理临时拒绝转发请求（5xx），可能是代理客户端过载，请稍后重试"
    if "tunnel connection failed: 4" in joined:
        return "代理拒绝转发请求（4xx），请检查代理是否需要鉴权或协议是否正确"
    if "connection refused" in joined or "actively refused" in joined:
        return "无法连接到本地代理端口，请确认代理工具正在运行且端口正确"
    if "connecttimeout" in joined or "connect timed out" in joined:
        return "连接代理超时，请检查主机/端口是否填对"
    if "nameresolution" in joined or "failed to establish" in joined or "name or service not known" in joined:
        return "网络异常或代理地址解析失败"
    if "ssl" in joined or "certificate" in joined:
        return "SSL/证书错误"
    return "代理或目标服务不可达，请稍后重试"


def check_public_ip(use_proxy: bool = False, proxy_url: str | None = None) -> dict[str, Any]:
    """
    取当前出口 IP + 归属地。

    走多家服务 fallback —— 首选 ip-api.com，失败时依次降级到 ifconfig.co / ipify+ipapi.co，
    都失败才抛 ProxyCheckError。国内访问 ip-api.com 偶有不稳，fallback 能显著降低单点故障。
    """
    source = "proxy" if use_proxy else "direct"
    session = _build_session(use_proxy=use_proxy, proxy_url_override=proxy_url)

    errors: list[str] = []
    try:
        for name, fn in _PROVIDERS:
            try:
                info = fn(session)
                return {
                    "source": source,
                    "provider": name,
                    "ip": info["ip"],
                    "country": info["country"],
                    "region": info["region"],
                    "city": info["city"],
                    "isp": info["isp"],
                    "checked_at": datetime.now().isoformat(timespec="seconds"),
                }
            except Exception as e:
                errors.append(f"{name}: {e}")
                logger.warning(f"[{source}] IP 检测源 {name} 失败：{e}")
                continue
    finally:
        session.close()

    # 完整堆栈只走日志，抛给上层的 message 用归类后的友好短文案
    logger.warning(f"[{source}] 所有 IP 检测源均失败：{' | '.join(errors)}")
    raise ProxyCheckError(_friendly_proxy_error(errors))


def check_configured_proxy(
    strict_same_ip: bool = True,
    require_direct_success: bool = False,
) -> dict[str, Any]:
    """
    对配置的代理做完整体检。

    Args:
        strict_same_ip: 若代理出口 IP 与直连出口 IP 相同，则认为代理没生效，拒绝上传。
        require_direct_success: 若直连 IP 检测失败也判失败。默认 False 时，直连失败仅
            打 WARN 并在返回结果中标记 `direct_failed=True`，让调用方/UI 自行决策。

    Returns:
        dict: {
            "enabled": bool,
            "proxy_url": str,
            "proxy": {ip, country, region, city, isp, provider, ...},
            "direct": {...} 或 None,
            "direct_error": str | None,
            "direct_failed": bool,           # 直连检测是否失败（独立验证不可得）
        }
    """
    if not WeixinConfig.PROXY_ENABLED:
        return {"enabled": False, "message": "proxy disabled"}

    url = proxy_url()
    if not url:
        raise ProxyCheckError("已开启代理但缺少主机或端口配置")

    proxy_info = check_public_ip(use_proxy=True, proxy_url=url)
    direct_info = None
    direct_error: str | None = None

    try:
        direct_info = check_public_ip(use_proxy=False)
    except Exception as e:
        direct_error = str(e)

    direct_failed = direct_info is None
    if direct_failed:
        # 直连失败 = 我们没法独立确认代理 IP 不等于本机出口 IP。整机走 VPN 的情况下，
        # 代理 IP 看起来"对"但实际就是本机出口。这里只 WARN，是否拒绝交由上层 / 配置控制。
        logger.warning(
            f"直连 IP 检测失败，无法独立验证代理是否生效（direct_error={direct_error}）。"
            f"代理出口 IP={proxy_info.get('ip') or '-'}"
        )
        if require_direct_success:
            raise ProxyCheckError(
                f"无法独立验证代理出口（直连检测失败：{direct_error}）。"
                f"如确认本机已通过其他方式走代理，请在设置中关闭严格直连校验。"
            )

    if (
        strict_same_ip
        and direct_info
        and proxy_info.get("ip")
        and proxy_info.get("ip") == direct_info.get("ip")
    ):
        raise ProxyCheckError(
            f"代理出口 IP 与直连 IP 相同 ({proxy_info['ip']})，代理可能未生效；已拒绝上传。"
        )

    return {
        "enabled": True,
        "proxy_url": url,
        "proxy": proxy_info,
        "direct": direct_info,
        "direct_error": direct_error,
        "direct_failed": direct_failed,
    }


# ---------- 进程级 TTL 缓存 ----------

_check_cache_lock = threading.Lock()
_check_cache: dict[str, Any] = {
    "key": None,           # (proxy_url, strict_same_ip)
    "result": None,        # 上次成功的 check_configured_proxy 返回值
    "checked_at": 0.0,     # time.time()
}


def _cache_key(strict_same_ip: bool, proxy_url_override: str | None = None) -> tuple[str, bool]:
    return (proxy_url_override or proxy_url(), strict_same_ip)


def invalidate_proxy_check_cache() -> None:
    """配置变更时调用，下次检测重新打网。"""
    with _check_cache_lock:
        _check_cache["key"] = None
        _check_cache["result"] = None
        _check_cache["checked_at"] = 0.0


def log_proxy_check_for_upload(
    strict_same_ip: bool = True,
    use_cache: bool = True,
    ttl_seconds: int | None = None,
    proxy_url: str | None = None,
) -> dict[str, Any] | None:
    """
    上传前的代理体检。批量任务里同一批通常共享 TTL 缓存，避免 50 个任务打 100 次 ip-api。

    Args:
        strict_same_ip: 透传给 `check_configured_proxy`。
        use_cache: 是否复用缓存。前端"测试代理"按钮走 False，强制实测。
        ttl_seconds: 自定义 TTL；默认 `PROXY_CHECK_TTL_SECONDS`。

    Returns:
        - None：代理未启用，调用方应跳过代理逻辑。
        - dict：`check_configured_proxy` 的返回值（可能来自缓存）。
    """
    if not proxy_url and not WeixinConfig.PROXY_ENABLED:
        return None

    ttl = PROXY_CHECK_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    key = _cache_key(strict_same_ip, proxy_url)
    now = time.time()

    if use_cache:
        with _check_cache_lock:
            cached_key = _check_cache["key"]
            cached_result = _check_cache["result"]
            cached_at = _check_cache["checked_at"]
        if (
            cached_key == key
            and cached_result is not None
            and now - cached_at <= ttl
        ):
            info = cached_result.get("proxy") or {}
            logger.info(
                f"复用代理检测缓存（{int(now - cached_at)}s 前测过）：ip={info.get('ip') or '-'}"
            )
            return cached_result

    if proxy_url:
        proxy_info = check_public_ip(use_proxy=True, proxy_url=proxy_url)
        result = {
            "enabled": True,
            "proxy_url": proxy_url,
            "proxy": proxy_info,
            "direct": None,
            "direct_error": None,
            "direct_failed": True,
        }
    else:
        result = check_configured_proxy(strict_same_ip=strict_same_ip)
    info = result.get("proxy") or {}
    location = " ".join(
        part for part in (info.get("country"), info.get("region"), info.get("city")) if part
    )
    logger.info(
        f"视频号上传代理就绪：ip={info.get('ip') or '-'} 位置={location or '-'} "
        f"来源={info.get('provider') or '-'}"
    )

    with _check_cache_lock:
        _check_cache["key"] = key
        _check_cache["result"] = result
        _check_cache["checked_at"] = now

    return result


def profile_proxy_url(profile: dict) -> str:
    return f"{profile.get('scheme') or 'http'}://{profile.get('host')}:{int(profile.get('port'))}"


def check_profile(profile: dict) -> dict[str, Any]:
    url = profile_proxy_url(profile)
    return check_public_ip(use_proxy=True, proxy_url=url)
