"""
视频号消息中心：作品优化建议
"""

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

from DrissionPage import ChromiumPage

from src.core.logger import logger

NOTIFICATION_LIST_API = (
    "https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin/"
    "notification/notification_list"
)
OPTIMIZE_TIP_TITLE = "作品优化建议"
PAGE_SIZE = 20
MAX_PAGES = 50

_TITLE_RE = re.compile(r"作品标题[：:]\s*(.+)")
_PUBLISHED_RE = re.compile(
    r"发布时间[：:]\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
)
_EXPORT_ID_RE = re.compile(r"(?:export_id|exportId)=([^&]+)", re.I)


@dataclass
class OptimizeTipNotice:
    """一条作品优化建议通知"""

    post_id: str
    title: Optional[str]
    published_at: Optional[datetime]
    msgid: Optional[str]
    content: str
    ref_url: str


def extract_export_id_from_ref_url(ref_url: str) -> Optional[str]:
    """从了解详情链接中解析 export_id。"""
    if not ref_url:
        return None
    match = _EXPORT_ID_RE.search(ref_url)
    if match:
        return match.group(1).strip()
    try:
        parsed = urlparse(ref_url)
        qs = parse_qs(parsed.query)
        for key in ("export_id", "exportId", "objectId"):
            vals = qs.get(key)
            if vals and vals[0]:
                return vals[0].strip()
    except Exception:
        pass
    return None


def parse_optimize_tip_content(content: str) -> tuple:
    """从通知正文解析作品标题与发布时间。"""
    title = None
    published_at = None
    text = content or ""
    m_title = _TITLE_RE.search(text)
    if m_title:
        title = m_title.group(1).strip().split("\n")[0].strip()
        # 常见截断省略号
        if title.endswith("……"):
            title = title[:-2].rstrip("…").rstrip(".")
    m_pub = _PUBLISHED_RE.search(text)
    if m_pub:
        try:
            published_at = datetime.strptime(m_pub.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            published_at = None
    return title, published_at


def parse_optimize_tip_item(item: dict) -> Optional[OptimizeTipNotice]:
    """解析 notification_list 单条「作品优化建议」。"""
    if not isinstance(item, dict):
        return None
    if (item.get("title") or "").strip() != OPTIMIZE_TIP_TITLE:
        return None
    ref_url = str(item.get("refUrl") or item.get("ref_url") or "")
    post_id = extract_export_id_from_ref_url(ref_url)
    if not post_id:
        return None
    content = str(item.get("content") or "")
    title, published_at = parse_optimize_tip_content(content)
    return OptimizeTipNotice(
        post_id=post_id,
        title=title,
        published_at=published_at,
        msgid=str(item.get("msgid") or "") or None,
        content=content,
        ref_url=ref_url,
    )


def _notif_body(current_page: int, req_type: int = 1) -> dict:
    return {
        "pageSize": PAGE_SIZE,
        "currentPage": current_page,
        "reqType": req_type,
        "timestamp": str(int(time.time() * 1000)),
        "_log_finder_uin": "",
        "_log_finder_id": "",
        "rawKeyBuff": "",
        "pluginSessionId": None,
        "scene": 7,
        "reqScene": 7,
    }


def _fetch_notification_page(page: ChromiumPage, current_page: int) -> dict:
    body_json = json.dumps(_notif_body(current_page, req_type=1), ensure_ascii=False)
    js = f"""
    return (async function() {{
      const resp = await fetch({json.dumps(NOTIFICATION_LIST_API)}, {{
        method: 'POST',
        credentials: 'include',
        headers: {{ 'Content-Type': 'application/json' }},
        body: {json.dumps(body_json)}
      }});
      const text = await resp.text();
      try {{
        return {{ ok: resp.ok || resp.status === 201, status: resp.status, body: JSON.parse(text) }};
      }} catch (e) {{
        return {{ ok: false, status: resp.status, raw: text.slice(0, 500) }};
      }}
    }})();
    """
    result = page.run_js(js)
    if not isinstance(result, dict):
        raise RuntimeError(f"notification_list 返回非对象: {result!r}")
    return result


def fetch_optimize_tip_notices(
    page: ChromiumPage, max_pages: int = MAX_PAGES
) -> List[OptimizeTipNotice]:
    """拉取消息中心中的「作品优化建议」并解析作品 ID。"""
    # 确保在 channels 域下（与 post_list 共用会话）
    url = str(getattr(page, "url", "") or "")
    if "channels.weixin.qq.com" not in url:
        page.get("https://channels.weixin.qq.com/platform/notification/notificationList")
        time.sleep(1.0)

    notices: List[OptimizeTipNotice] = []
    seen: set = set()

    for current_page in range(1, min(max_pages, MAX_PAGES) + 1):
        try:
            raw = _fetch_notification_page(page, current_page)
        except Exception as e:
            logger.warning(f"notification_list 第 {current_page} 页异常: {e}")
            break

        body = raw.get("body")
        if not isinstance(body, dict):
            break
        err_code = body.get("errCode", 0)
        if err_code not in (0, None, "0"):
            logger.warning(f"notification_list 业务错误: {body}")
            break

        data = body.get("data") or {}
        items = data.get("list") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items:
            break

        for item in items:
            notice = parse_optimize_tip_item(item)
            if notice and notice.post_id not in seen:
                seen.add(notice.post_id)
                notices.append(notice)

        if len(items) < PAGE_SIZE:
            break
        time.sleep(0.25)

    logger.info(f"已解析作品优化建议 {len(notices)} 条")
    return notices
