"""
抖音视频下载工具 - 使用示例集合

本文件包含多个实用示例，展示如何使用抖音视频下载工具
"""

# ============================================================================
# 示例 1: 基础使用 - 获取下载链接
# ============================================================================

def example_1_get_download_link():
    """
    最简单的使用方式：获取视频下载链接
    
    场景: 你只需要获取无水印的下载链接，不需要下载文件
    """
    from tools import get_douyin_download_link
    
    # 分享链接
    share_link = "https://v.douyin.com/xxxxx"
    
    # 获取下载链接
    result = get_douyin_download_link(share_link)
    
    # 检查结果
    if result['status'] == 'success':
        print(f"✅ 成功获取下载链接")
        print(f"视频ID: {result['video_id']}")
        print(f"标题: {result['title']}")
        print(f"下载链接: {result['download_url']}")
    else:
        print(f"❌ 失败: {result['message']}")


# ============================================================================
# 示例 2: 下载视频 - 基础版
# ============================================================================

def example_2_download_video_basic():
    """
    基础下载：下载视频到默认目录
    
    场景: 你需要下载视频文件到 .data 目录
    """
    from tools import download_douyin_video
    
    # 分享链接
    share_link = "https://v.douyin.com/xxxxx"
    
    # 下载视频
    result = download_douyin_video(share_link)
    
    # 检查结果
    if result['status'] == 'success':
        print(f"✅ 下载完成")
        print(f"标题: {result['title']}")
        print(f"文件路径: {result['file_path']}")
    else:
        print(f"❌ 下载失败: {result['message']}")


# ============================================================================
# 示例 3: 下载视频 - 带进度显示
# ============================================================================

def example_3_download_with_progress():
    """
    带进度显示的下载
    
    场景: 你需要看到实时的下载进度
    """
    from tools import download_douyin_video
    
    def show_progress(progress):
        """显示下载进度"""
        percentage = progress['percentage']
        downloaded_mb = progress['downloaded'] / (1024 * 1024)
        total_mb = progress['total'] / (1024 * 1024)
        
        # 创建进度条
        bar_length = 30
        filled = int(bar_length * percentage / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        print(f"\r进度: [{bar}] {percentage:.1f}% ({downloaded_mb:.1f}MB/{total_mb:.1f}MB)", 
              end='', flush=True)
    
    # 分享链接
    share_link = "https://v.douyin.com/xxxxx"
    
    # 下载视频并显示进度
    result = download_douyin_video(share_link, on_progress=show_progress)
    
    print()  # 换行
    
    if result['status'] == 'success':
        print(f"✅ 下载完成: {result['file_path']}")
    else:
        print(f"❌ 下载失败: {result['message']}")


# ============================================================================
# 示例 4: 批量下载多个视频
# ============================================================================

def example_4_batch_download():
    """
    批量下载多个视频
    
    场景: 你有多个分享链接，需要逐个下载
    """
    from tools import download_douyin_video
    
    # 分享链接列表
    links = [
        "https://v.douyin.com/link1",
        "https://v.douyin.com/link2",
        "https://v.douyin.com/link3",
    ]
    
    # 统计
    success_count = 0
    failed_count = 0
    
    for i, link in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] 正在处理...")
        
        result = download_douyin_video(link)
        
        if result['status'] == 'success':
            print(f"✅ 成功: {result['title']}")
            print(f"   文件: {result['file_path']}")
            success_count += 1
        else:
            print(f"❌ 失败: {result['message']}")
            failed_count += 1
    
    # 总结
    print(f"\n{'='*50}")
    print(f"下载完成: 成功 {success_count} 个，失败 {failed_count} 个")
    print(f"{'='*50}")


# ============================================================================
# 示例 5: 并发下载（使用线程池）
# ============================================================================

def example_5_concurrent_download():
    """
    并发下载多个视频
    
    场景: 你有很多视频需要下载，希望加快速度
    注意: 不要并发数过多，否则可能被服务器限流
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from tools import download_douyin_video
    
    # 分享链接列表
    links = [
        "https://v.douyin.com/link1",
        "https://v.douyin.com/link2",
        "https://v.douyin.com/link3",
        "https://v.douyin.com/link4",
    ]
    
    # 使用线程池（最多 3 个并发）
    with ThreadPoolExecutor(max_workers=3) as executor:
        # 提交所有任务
        futures = {
            executor.submit(download_douyin_video, link): link 
            for link in links
        }
        
        # 处理完成的任务
        completed = 0
        for future in as_completed(futures):
            completed += 1
            link = futures[future]
            try:
                result = future.result()
                if result['status'] == 'success':
                    print(f"[{completed}/{len(links)}] ✅ {result['title']}")
                else:
                    print(f"[{completed}/{len(links)}] ❌ {result['message']}")
            except Exception as e:
                print(f"[{completed}/{len(links)}] ❌ 异常: {e}")


# ============================================================================
# 示例 6: 使用 DouyinProcessor 类（更细粒度的控制）
# ============================================================================

def example_6_use_processor_class():
    """
    使用 DouyinProcessor 类获得更多控制
    
    场景: 你需要对每个步骤有更细粒度的控制
    """
    from douyin_processor import DouyinProcessor, DownloadProgress
    
    # 创建处理器实例
    # timeout: 请求超时时间（秒）
    # max_retries: 最大重试次数
    processor = DouyinProcessor(timeout=15, max_retries=5)
    
    try:
        # 步骤1: 解析分享链接
        print("正在解析链接...")
        video_info = processor.parse_share_url("https://v.douyin.com/xxxxx")
        print(f"✅ 解析成功: {video_info.title}")
        
        # 步骤2: 检查视频信息
        print(f"视频ID: {video_info.video_id}")
        print(f"下载URL: {video_info.url}")
        
        # 步骤3: 下载视频
        print("正在下载...")
        
        def progress_callback(progress: DownloadProgress):
            """进度回调函数"""
            percentage = progress.percentage
            downloaded_mb = progress.downloaded / (1024 * 1024)
            total_mb = progress.total / (1024 * 1024)
            print(f"\r下载进度: {percentage:.1f}% ({downloaded_mb:.1f}MB/{total_mb:.1f}MB)", 
                  end='', flush=True)
        
        file_path = processor.download_video(
            video_info,
            on_progress=progress_callback
        )
        
        print()
        print(f"✅ 下载完成: {file_path}")
        
    except Exception as e:
        print(f"❌ 出错: {e}")


# ============================================================================
# 示例 7: 错误处理和重试
# ============================================================================

def example_7_error_handling_and_retry():
    """
    完善的错误处理和重试机制
    
    场景: 网络不稳定，需要自动重试
    """
    from tools import download_douyin_video
    from time import sleep
    
    share_link = "https://v.douyin.com/xxxxx"
    max_attempts = 3
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        print(f"尝试 {attempt}/{max_attempts}...")
        
        try:
            result = download_douyin_video(share_link)
            
            if result['status'] == 'success':
                print(f"✅ 成功: {result['file_path']}")
                break  # 成功，退出循环
            else:
                print(f"⚠️  下载失败: {result['message']}")
                
                if attempt < max_attempts:
                    print(f"等待 5 秒后重试...")
                    sleep(5)
        
        except Exception as e:
            print(f"⚠️  异常: {e}")
            
            if attempt < max_attempts:
                print(f"等待 5 秒后重试...")
                sleep(5)
    
    if attempt == max_attempts:
        print(f"❌ 经过 {max_attempts} 次尝试，仍然失败")


# ============================================================================
# 示例 8: 解析视频信息（不下载）
# ============================================================================

def example_8_parse_video_info():
    """
    只解析视频信息，不下载
    
    场景: 你只想获取视频的元信息
    """
    from tools import parse_douyin_video_info
    
    share_link = "https://v.douyin.com/xxxxx"
    
    result = parse_douyin_video_info(share_link)
    
    if result['status'] == 'success':
        print(f"视频ID: {result['video_id']}")
        print(f"标题: {result['title']}")
        print(f"下载链接: {result['download_url']}")
        print(f"描述: {result.get('description', '暂无描述')}")
    else:
        print(f"❌ 解析失败: {result['message']}")


# ============================================================================
# 示例 9: 从文件读取链接列表
# ============================================================================

def example_9_read_links_from_file():
    """
    从文件读取分享链接，然后下载
    
    场景: 你有一个文件包含多个分享链接
    
    文件格式 (links.txt):
    https://v.douyin.com/link1
    https://v.douyin.com/link2
    https://v.douyin.com/link3
    """
    from tools import download_douyin_video
    
    # 读取文件中的链接
    try:
        with open('links.txt', 'r', encoding='utf-8') as f:
            links = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("❌ 找不到 links.txt 文件")
        return
    
    # 下载每个视频
    for i, link in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] {link}")
        
        result = download_douyin_video(link)
        
        if result['status'] == 'success':
            print(f"✅ {result['title']}")
        else:
            print(f"❌ {result['message']}")


# ============================================================================
# 示例 10: 完整的应用场景（集合所有特性）
# ============================================================================

def example_10_complete_application():
    """
    完整的应用示例：结合多个特性
    
    功能:
    1. 从用户输入读取链接
    2. 验证链接有效性
    3. 显示视频信息
    4. 下载视频并显示进度
    5. 错误处理和重试
    6. 最后显示统计信息
    """
    from tools import parse_douyin_video_info, download_douyin_video
    from time import sleep
    
    def download_with_validation(link, max_retries=3):
        """带验证和重试的下载函数"""
        
        # 步骤1: 验证和解析链接
        print("📍 验证链接...")
        info_result = parse_douyin_video_info(link)
        
        if info_result['status'] != 'success':
            print(f"❌ 链接无效: {info_result['message']}")
            return False
        
        print(f"✅ 链接有效")
        print(f"   标题: {info_result['title']}")
        print(f"   ID: {info_result['video_id']}")
        
        # 步骤2: 下载视频（带重试）
        for attempt in range(1, max_retries + 1):
            print(f"\n📥 下载 (尝试 {attempt}/{max_retries})...")
            
            def progress_callback(progress):
                percentage = progress['percentage']
                bar_length = 20
                filled = int(bar_length * percentage / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"\r  [{bar}] {percentage:.1f}%", end='', flush=True)
            
            result = download_douyin_video(link, on_progress=progress_callback)
            
            print()  # 换行
            
            if result['status'] == 'success':
                print(f"✅ 下载完成: {result['file_path']}")
                return True
            else:
                print(f"⚠️  下载失败: {result['message']}")
                
                if attempt < max_retries:
                    print(f"   等待 3 秒后重试...")
                    sleep(3)
        
        print(f"❌ 经过 {max_retries} 次尝试，下载失败")
        return False
    
    # 示例使用
    links = [
        "https://v.douyin.com/link1",
        "https://v.douyin.com/link2",
    ]
    
    success_count = 0
    failed_count = 0
    
    for i, link in enumerate(links, 1):
        print(f"\n{'='*50}")
        print(f"视频 {i}/{len(links)}")
        print(f"{'='*50}")
        
        if download_with_validation(link):
            success_count += 1
        else:
            failed_count += 1
    
    # 显示统计
    print(f"\n{'='*50}")
    print(f"完成统计")
    print(f"{'='*50}")
    print(f"成功: {success_count}")
    print(f"失败: {failed_count}")
    print(f"总计: {len(links)}")


# ============================================================================
# 主函数
# ============================================================================

if __name__ == '__main__':
    import sys
    
    examples = {
        '1': ('获取下载链接', example_1_get_download_link),
        '2': ('下载视频-基础版', example_2_download_video_basic),
        '3': ('下载视频-带进度', example_3_download_with_progress),
        '4': ('批量下载', example_4_batch_download),
        '5': ('并发下载', example_5_concurrent_download),
        '6': ('使用 Processor 类', example_6_use_processor_class),
        '7': ('错误处理和重试', example_7_error_handling_and_retry),
        '8': ('解析视频信息', example_8_parse_video_info),
        '9': ('从文件读取链接', example_9_read_links_from_file),
        '10': ('完整应用示例', example_10_complete_application),
    }
    
    print("抖音视频下载工具 - 使用示例")
    print("="*50)
    
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        if example_num in examples:
            title, func = examples[example_num]
            print(f"运行示例 {example_num}: {title}")
            print("="*50)
            try:
                func()
            except Exception as e:
                print(f"❌ 出错: {e}")
        else:
            print(f"❌ 无效的示例编号: {example_num}")
    else:
        print("可用示例:")
        for num, (title, _) in examples.items():
            print(f"  {num}. {title}")
        print("\n使用方式: python examples.py <示例编号>")
        print("示例: python examples.py 3")
