import asyncio
import json
from playwright.async_api import async_playwright

async def search_douyin_videos(keyword: str, max_videos: int = 20):
    """
    在抖音网页版搜索关键词，返回视频列表（基础信息）。
    注意：抖音页面高度动态化，此示例可能随 DOM 变化而失效，需自行调整选择器。
    """
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,        # 建议先设 False 观察是否正常，调试后可改为 True
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # 访问搜索页
        search_url = f'https://www.douyin.com/search/{keyword}?type=general'
        await page.goto(search_url, wait_until='networkidle')
        await page.wait_for_timeout(3000)  # 等待异步数据加载

        # 获取视频卡片列表（选择器需根据当前页面调整，这里以 2024 年常见结构为例）
        cards = await page.query_selector_all('ul[data-e2e="scroll-list"] li')

        for card in cards[:max_videos]:
            try:
                # 视频链接
                link_el = await card.query_selector('a[href*="video"]')
                href = await link_el.get_attribute('href') if link_el else ''
                video_id = href.split('/')[-1] if href else ''

                # 标题
                title_el = await card.query_selector('.B3AsdZT9')  # 需确认实际 class
                title = await title_el.inner_text() if title_el else ''

                # 点赞数等（通常在底部 span 内）
                likes_el = await card.query_selector('.author-card .like-count')  # 示例
                likes = await likes_el.inner_text() if likes_el else ''

                if video_id:
                    results.append({
                        'video_id': video_id,
                        'title': title.strip(),
                        'likes': likes.strip(),
                        'url': f'https://www.douyin.com/video/{video_id}'
                    })
            except Exception:
                continue

        await browser.close()
    return results

if __name__ == '__main__':
    keyword = input('请输入搜索关键词: ')
    videos = asyncio.run(search_douyin_videos(keyword, max_videos=10))
    print(json.dumps(videos, ensure_ascii=False, indent=2))