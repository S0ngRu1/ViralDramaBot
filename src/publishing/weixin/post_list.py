"""
从视频号创作者中心拉取已发视频列表（播放量等）
"""

import json
import time
from datetime import datetime
from typing import Optional

from DrissionPage import ChromiumPage

from .channel_post import ChannelPost
from .config import WeixinConfig
from src.core.logger import logger

# HAR 确认：列表接口走 micro/content 前缀
POST_LIST_API = (
    "https://channels.weixin.qq.com/micro/content/"
    "cgi-bin/mmfinderassistant-bin/post/post_list"
)
PAGE_SIZE = 20
MAX_PAGES = 50


def parse_post_item(item: dict) -> Optional[ChannelPost]:
    """从 post_list 接口单条记录解析 ChannelPost（供单测复用）"""
    if not item or not isinstance(item, dict):
        return None
    post_id = (
        item.get("exportId")
        or item.get("export_id")
        or item.get("objectId")
        or item.get("object_id")
    )
    if not post_id:
        return None
    post_id = str(post_id)

    desc = item.get("desc") or {}
    if isinstance(desc, dict):
        title = (desc.get("description") or desc.get("title") or "").strip()
    else:
        title = str(desc).strip()

    create_time = item.get("createTime") or item.get("create_time")
    if create_time is None:
        return None
    try:
        ts = float(create_time)
        if ts > 1e12:
            ts /= 1000.0
        published_at = datetime.fromtimestamp(ts)
    except (TypeError, ValueError, OSError):
        return None

    read_count = item.get("readCount")
    if read_count is None:
        read_count = item.get("read_count") or item.get("playCount") or 0
    try:
        view_count = int(read_count)
    except (TypeError, ValueError):
        view_count = 0

    return ChannelPost(
        post_id=post_id,
        title=title or post_id,
        published_at=published_at,
        view_count=view_count,
    )


def _page_fetch_body(current_page: int) -> dict:
    return {
        "pageSize": PAGE_SIZE,
        "currentPage": current_page,
        "userpageType": 11,
        "stickyOrder": True,
        "timestamp": str(int(time.time() * 1000)),
        "_log_finder_uin": "",
        "_log_finder_id": "",
        "rawKeyBuff": "",
        "pluginSessionId": None,
        "scene": 7,
        "reqScene": 7,
    }


def _fetch_page_via_js(page: ChromiumPage, current_page: int) -> dict:
    """在已登录页面上下文中 POST post_list（自动携带 Cookie）"""
    body_json = json.dumps(_page_fetch_body(current_page), ensure_ascii=False)
    js = f"""
    return (async function() {{
      const resp = await fetch({json.dumps(POST_LIST_API)}, {{
        method: 'POST',
        credentials: 'include',
        headers: {{ 'Content-Type': 'application/json' }},
        body: {json.dumps(body_json)}
      }});
      const text = await resp.text();
      try {{
        return {{ ok: resp.ok, status: resp.status, body: JSON.parse(text) }};
      }} catch (e) {{
        return {{ ok: false, status: resp.status, raw: text.slice(0, 500) }};
      }}
    }})();
    """
    result = page.run_js(js)
    if not isinstance(result, dict):
        raise RuntimeError(f"post_list 返回非对象: {result!r}")
    return result


def _extract_list_from_response(body: dict) -> list:
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return []
    lst = data.get("list") or data.get("feeds") or data.get("items") or []
    return lst if isinstance(lst, list) else []


def _should_continue(body: dict, page_items: int) -> bool:
    data = body.get("data") if isinstance(body, dict) else None
    if isinstance(data, dict) and "continueFlag" in data:
        return bool(data.get("continueFlag"))
    return page_items >= PAGE_SIZE


def fetch_posts(
    page: ChromiumPage,
    max_pages: int = MAX_PAGES,
    published_after: Optional[datetime] = None,
) -> list:
    """
    拉取账号下已发视频列表（含播放量）。

    需先导航到 channels 域并完成 Cookie 登录。

    Args:
        published_after: 若提供，只保留 published_at >= 该时间的作品；
            且当某一页「最新作品」仍早于该时间时提前停止翻页（列表大致新→旧）。
    """
    page.get(WeixinConfig.POST_LIST_URL)
    time.sleep(1.5)

    posts: list = []
    seen_ids: set = set()

    for current_page in range(1, min(max_pages, MAX_PAGES) + 1):
        try:
            raw = _fetch_page_via_js(page, current_page)
        except Exception as e:
            logger.warning(f"post_list 第 {current_page} 页请求异常: {e}")
            break

        if not raw.get("ok") and raw.get("status") not in (200, 201):
            logger.warning(
                f"post_list HTTP 异常: status={raw.get('status')}, "
                f"raw={str(raw.get('raw', ''))[:200]}"
            )
            break

        body = raw.get("body")
        if not isinstance(body, dict):
            logger.warning(f"post_list 响应体异常: {body!r}")
            break

        err_code = body.get("errCode", body.get("ret", 0))
        if err_code not in (0, None, "0"):
            logger.warning(f"post_list 业务错误: {body}")
            break

        items = _extract_list_from_response(body)
        page_posts = []
        for item in items:
            parsed = parse_post_item(item)
            if not parsed or parsed.post_id in seen_ids:
                continue
            seen_ids.add(parsed.post_id)
            page_posts.append(parsed)
            if published_after is None or parsed.published_at >= published_after:
                posts.append(parsed)

        if not items or not _should_continue(body, len(items)):
            break

        # 整页最新一条仍早于窗口 → 后续页只会更旧，停止翻页
        if published_after is not None and page_posts:
            newest_on_page = max(p.published_at for p in page_posts)
            if newest_on_page < published_after:
                break

        time.sleep(0.3)

    logger.info(f"已拉取视频列表 {len(posts)} 条")
    return posts
