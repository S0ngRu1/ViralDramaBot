"""
在视频号创作者中心删除已发视频
"""

import json
import time
from typing import Optional

from DrissionPage import ChromiumPage

from src.core.logger import logger

DELETE_API_CANDIDATES = [
    "https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin/post/delete",
    "https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin/post/post_delete",
]


def _delete_via_api(page: ChromiumPage, post_id: str) -> bool:
    """在页面上下文中调用删除 CGI"""
    ts = int(time.time() * 1000)
    for api_url in DELETE_API_CANDIDATES:
        for body_key in ("exportId", "export_id", "objectId"):
            body_json = json.dumps({body_key: post_id, "timestamp": ts})
            js = f"""
            return (async function() {{
              const resp = await fetch({json.dumps(api_url)}, {{
                method: 'POST',
                credentials: 'include',
                headers: {{ 'Content-Type': 'application/json' }},
                body: {json.dumps(body_json)}
              }});
              const text = await resp.text();
              try {{
                const body = JSON.parse(text);
                const code = body.errCode ?? body.ret ?? body.code;
                return {{ ok: resp.ok, code: code, body: body }};
              }} catch (e) {{
                return {{ ok: resp.ok, raw: text.slice(0, 300) }};
              }}
            }})();
            """
            try:
                result = page.run_js(js)
            except Exception as e:
                logger.debug(f"删除 API 调用异常 ({api_url}): {e}")
                continue
            if not isinstance(result, dict):
                continue
            code = result.get("code")
            if code in (0, None, "0"):
                logger.info(f"平台 API 删除成功: post_id={post_id}")
                return True
            if result.get("ok"):
                logger.info(f"平台 API 删除可能成功: post_id={post_id}, result={result}")
                return True
    return False


def _delete_via_dom(page: ChromiumPage, post_id: str, title: Optional[str]) -> bool:
    """在列表页通过菜单点击删除"""
    js_find = r"""
    (function (postId, titleHint) {
      var nodes = document.querySelectorAll(
        '[data-export-id], [data-id], [class*="post"], [class*="feed-item"], tr'
      );
      for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        var id = el.getAttribute('data-export-id')
          || el.getAttribute('data-id') || '';
        var text = (el.innerText || '').trim();
        if (id && String(id) === String(postId)) { el.scrollIntoView({block:'center'}); el.click(); return 'row'; }
        if (titleHint && text.indexOf(titleHint) >= 0) {
          el.scrollIntoView({block:'center'});
          var more = el.querySelector('[class*="more"], [class*="action"], button');
          if (more) { more.click(); return 'menu'; }
        }
      }
      return null;
    })(%s, %s);
    """ % (json.dumps(post_id), json.dumps(title or ""))

    try:
        page.run_js(js_find)
        time.sleep(0.5)
    except Exception:
        pass

    delete_selectors = [
        "xpath://*[contains(text(),'删除') and not(contains(text(),'删除账号'))]",
        "css:.weui-desktop-popover [class*='delete']",
        "css:[class*='menu'] [class*='delete']",
    ]
    for sel in delete_selectors:
        try:
            btn = page.ele(sel, timeout=1)
            if btn:
                btn.click()
                time.sleep(0.3)
                break
        except Exception:
            continue

    confirm_selectors = [
        "xpath://button[contains(.,'删除')]",
        "xpath://*[contains(@class,'dialog')]//*[contains(text(),'删除')]",
        "css:.weui-desktop-dialog__ft .weui-desktop-btn_primary",
    ]
    for sel in confirm_selectors:
        try:
            confirm = page.ele(sel, timeout=2)
            if confirm and "删除" in (confirm.text or ""):
                confirm.click()
                time.sleep(1)
                return True
        except Exception:
            continue
    return False


def delete_post(
    page: ChromiumPage,
    post_id: str,
    title: Optional[str] = None,
) -> bool:
    """
    删除指定视频。优先 CGI，失败则 DOM 操作。
    """
    if post_id.startswith("dom_"):
        return _delete_via_dom(page, post_id, title)

    if _delete_via_api(page, post_id):
        return True

    logger.info(f"API 删除未成功，尝试 DOM: post_id={post_id}")
    return _delete_via_dom(page, post_id, title)
