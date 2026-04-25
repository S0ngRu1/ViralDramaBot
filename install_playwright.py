#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安装Playwright依赖脚本
"""

import subprocess
import sys
import os


def install_playwright():
    """安装Playwright"""
    print("🚀 安装Playwright依赖")
    print("=" * 60)

    # 检查Python版本
    print(f"🐍 Python版本: {sys.version}")
    print()

    # 安装Playwright包
    print("1️⃣ 安装Playwright Python包...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        print("✅ Playwright包安装成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ Playwright包安装失败: {e}")
        return False

    # 安装浏览器
    print("\n2️⃣ 安装浏览器...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("✅ 浏览器安装成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ 浏览器安装失败: {e}")
        print("请手动运行: playwright install chromium")
        return False

    # 验证安装
    print("\n3️⃣ 验证安装...")
    try:
        import playwright
        from playwright.async_api import async_playwright
        print("✅ Playwright导入成功")

        # 测试版本
        import pkg_resources
        version = pkg_resources.get_distribution("playwright").version
        print(f"📦 Playwright版本: {version}")

        return True

    except ImportError as e:
        print(f"❌ Playwright导入失败: {e}")
        return False


def install_other_deps():
    """安装其他依赖"""
    print("\n📦 安装其他依赖...")

    dependencies = [
        "requests",
        "beautifulsoup4",
        "lxml",
    ]

    for dep in dependencies:
        print(f"安装 {dep}...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", dep], check=True)
            print(f"✅ {dep} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ {dep} 安装失败: {e}")

    print("\n✅ 所有依赖安装完成")


def create_test_script():
    """创建测试脚本"""
    print("\n🧪 创建测试脚本...")

    test_script = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Playwright快速测试
"""

import asyncio
import sys

async def test_playwright():
    try:
        from playwright.async_api import async_playwright

        print("🚀 启动Playwright测试...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            page = await context.new_page()

            print("🌐 访问测试页面...")
            await page.goto("https://www.example.com")

            title = await page.title()
            print(f"📄 页面标题: {title}")

            await browser.close()

        print("✅ Playwright测试成功！")
        return True

    except ImportError as e:
        print(f"❌ Playwright导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_playwright())
    sys.exit(0 if result else 1)
'''

    with open("test_playwright.py", "w", encoding="utf-8") as f:
        f.write(test_script)

    os.chmod("test_playwright.py", 0o755)
    print("✅ 测试脚本已创建: test_playwright.py")


def main():
    """主函数"""
    print("=" * 60)
    print("抖音视频搜索工具 - 依赖安装")
    print("=" * 60)

    # 安装Playwright
    if not install_playwright():
        print("\n❌ Playwright安装失败")
        print("请手动运行以下命令:")
        print("  pip install playwright")
        print("  playwright install chromium")
        return

    # 安装其他依赖
    install_other_deps()

    # 创建测试脚本
    create_test_script()

    print("\n" + "=" * 60)
    print("🎉 安装完成！")
    print("\n下一步:")
    print("1. 运行测试: python test_playwright.py")
    print("2. 搜索视频: python example_search.py <关键词> --method playwright")
    print("3. 查看帮助: python example_search.py --help")
    print("=" * 60)


if __name__ == "__main__":
    main()