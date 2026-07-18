"""
在视频号创作者中心删除已发视频
"""

import json
import time
from typing import Optional

from DrissionPage import ChromiumPage

from src.core.logger import logger

# HAR 确认：删稿接口
POST_DELETE_API = (
    "https://channels.weixin.qq.com/micro/content/"
    "cgi-bin/mmfinderassistant-bin/post/post_delete"
)


def delete_post_via_api(page: ChromiumPage, post_id: str) -> bool:
    """在页面上下文中调用 post_delete（body.objectId）"""
    body = {
        "objectId": post_id,
        "timestamp": str(int(time.time() * 1000)),
        "_log_finder_uin": "",
        "_log_finder_id": "",
        "rawKeyBuff": "",
        "pluginSessionId": None,
        "scene": 7,
        "reqScene": 7,
    }
    body_json = json.dumps(body, ensure_ascii=False)
    js = f"""
    return (async function() {{
      const resp = await fetch({json.dumps(POST_DELETE_API)}, {{
        method: 'POST',
        credentials: 'include',
        headers: {{ 'Content-Type': 'application/json' }},
        body: {json.dumps(body_json)}
      }});
      const text = await resp.text();
      try {{
        const parsed = JSON.parse(text);
        const code = parsed.errCode ?? parsed.ret ?? parsed.code;
        const base = (parsed.data && parsed.data.baseResp) || {{}};
        const baseCode = base.errcode ?? base.errCode;
        return {{
          ok: resp.ok || resp.status === 201,
          status: resp.status,
          code: code,
          baseCode: baseCode,
          body: parsed
        }};
      }} catch (e) {{
        return {{ ok: false, status: resp.status, raw: text.slice(0, 300) }};
      }}
    }})();
    """
    try:
        result = page.run_js(js)
    except Exception as e:
        logger.warning(f"删除 API 调用异常: {e}")
        return False

    if not isinstance(result, dict):
        return False

    code = result.get("code")
    base_code = result.get("baseCode")
    if code in (0, None, "0") and base_code in (0, None, "0"):
        logger.info(f"平台 API 删除成功: post_id={post_id}")
        return True
    if result.get("ok") and code in (0, None, "0"):
        logger.info(f"平台 API 删除成功: post_id={post_id}, result={result}")
        return True

    logger.warning(f"平台 API 删除失败: post_id={post_id}, result={result}")
    return False


def delete_post(
    page: ChromiumPage,
    post_id: str,
    title: Optional[str] = None,
) -> bool:
    """删除指定视频（HAR 确认的 post_delete）。"""
    _ = title  # 保留签名兼容
    return delete_post_via_api(page, post_id)
