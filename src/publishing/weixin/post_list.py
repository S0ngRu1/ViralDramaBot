"""
从视频号创作者中心拉取已发视频列表（播放量等）
"""

import json
import time
from datetime import datetime
from typing import Any, Optional

from DrissionPage import ChromiumPage

from .channel_post import ChannelPost
from .config import WeixinConfig
from src.core.logger import logger

POST_LIST_API = (
    "https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin/post/post_list"
)
PAGE_SIZE = 20
MAX_PAGES = 50


def _parse_post_item(item: dict) -> Optional[ChannelPost]:
    """从 post_list 接口单条记录解析 ChannelPost"""
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


def _fetch_page_via_js(page: ChromiumPage, current_page: int) -> dict:
    """在已登录页面上下文中 POST post_list（自动携带 Cookie）"""
    ts = int(time.time() * 1000)
    body_json = json.dumps(
        {"currentPage": current_page, "pageSize": PAGE_SIZE, "timestamp": ts},
        ensure_ascii=False,
    )
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


def _extract_list_from_response(body: dict) -> list[dict]:
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return []
    lst = data.get("list") or data.get("feeds") or data.get("items") or []
    return lst if isinstance(lst, list) else []


def _total_pages_from_response(body: dict, page_items: int) -> int:
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return 1 if page_items else 0
    total = data.get("totalCount") or data.get("total") or data.get("feedsCount")
    if total is not None:
        try:
            return max(1, (int(total) + PAGE_SIZE - 1) // PAGE_SIZE)
        except (TypeError, ValueError):
            pass
    if page_items < PAGE_SIZE:
        return 1
    return MAX_PAGES


def fetch_posts(page: ChromiumPage, max_pages: int = MAX_PAGES) -> list[ChannelPost]:
    """
    拉取账号下已发视频列表（含播放量）。

    需先导航到 channels 域并完成 Cookie 登录。
    """
    page.get(WeixinConfig.POST_LIST_URL)
    time.sleep(2)

    posts: list[ChannelPost] = []
    seen_ids: set[str] = set()
    total_pages = 1

    for current_page in range(1, min(max_pages, MAX_PAGES) + 1):
        if current_page > total_pages:
            break
        try:
            raw = _fetch_page_via_js(page, current_page)
        except Exception as e:
            logger.warning(f"post_list 第 {current_page} 页请求异常: {e}")
            if current_page == 1:
                posts.extend(_fetch_posts_from_dom(page))
            break

        if not raw.get("ok"):
            logger.warning(
                f"post_list HTTP 异常: status={raw.get('status')}, "
                f"raw={raw.get('raw', '')[:200]}"
            )
            if current_page == 1:
                posts.extend(_fetch_posts_from_dom(page))
            break

        body = raw.get("body")
        if not isinstance(body, dict):
            logger.warning(f"post_list 响应体异常: {body!r}")
            if current_page == 1:
                posts.extend(_fetch_posts_from_dom(page))
            break

        err_code = body.get("errCode", body.get("ret", 0))
        if err_code not in (0, None, "0"):
            logger.warning(f"post_list 业务错误: {body}")
            if current_page == 1:
                posts.extend(_fetch_posts_from_dom(page))
            break

        items = _extract_list_from_response(body)
        if current_page == 1:
            total_pages = min(_total_pages_from_response(body, len(items)), max_pages)

        for item in items:
            parsed = _parse_post_item(item)
            if parsed and parsed.post_id not in seen_ids:
                seen_ids.add(parsed.post_id)
                posts.append(parsed)

        if len(items) < PAGE_SIZE:
            break
        time.sleep(0.3)

    logger.info(f"已拉取视频列表 {len(posts)} 条")
    return posts


def _fetch_posts_from_dom(page: ChromiumPage) -> list[ChannelPost]:
    """DOM 兜底：从列表页文本解析（精度较低）"""
    js = r"""
    (function () {
      var rows = [];
      var candidates = document.querySelectorAll(
        '[class*="post"], [class*="feed"], [class*="video-item"], tr, .weui-desktop-card'
      );
      candidates.forEach(function (el) {
        var t = (el.innerText || '').replace(/\s+/g, ' ').trim();
        if (!t || t.length < 4) return;
        var playMatch = t.match(/(?:播放|阅读量|浏览)[^\d]*(\d[\d,.]*[万千]?)/);
        var view = 0;
        if (playMatch) {
          var s = playMatch[1].replace(/,/g, '');
          if (s.indexOf('万') >= 0) view = Math.round(parseFloat(s) * 10000) || 0;
          else if (s.indexOf('千') >= 0) view = Math.round(parseFloat(s) * 1000) || 0;
          else view = parseInt(s, 10) || 0;
        }
        var id = el.getAttribute('data-id')
          || el.getAttribute('data-export-id')
          || el.getAttribute('data-object-id');
        if (!id) {
          var link = el.querySelector('a[href*="export"], a[href*="object"]');
          if (link && link.href) id = link.href;
        }
        if (!id) id = 'dom_' + rows.length;
        var lines = t.split(' ').filter(Boolean);
        var title = lines[0] || t.slice(0, 80);
        rows.push({ post_id: String(id), title: title, view_count: view, published_at: null });
      });
      return rows.slice(0, 100);
    })();
    """
    try:
        raw_rows = page.run_js(js) or []
    except Exception as e:
        logger.warning(f"DOM 解析视频列表失败: {e}")
        return []

    posts: list[ChannelPost] = []
    now = datetime.now()
    for i, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            continue
        posts.append(
            ChannelPost(
                post_id=str(row.get("post_id") or f"dom_{i}"),
                title=str(row.get("title") or ""),
                published_at=now,
                view_count=int(row.get("view_count") or 0),
            )
        )
    return posts
