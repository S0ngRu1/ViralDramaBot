#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音视频搜索启动脚本
"""

import sys
import os
import subprocess
import webbrowser


def print_banner():
    """打印横幅"""
    print("=" * 70)
    print("🎬 抖音视频搜索下载器")
    print("=" * 70)
    print()


def print_menu():
    """打印菜单"""
    print("请选择操作:")
    print("  1. 🔍 搜索视频（命令行）")
    print("  2. 🌐 启动Web界面")
    print("  3. 🧪 运行功能测试")
    print("  4. 🛠️  安装依赖 (Playwright)")
    print("  5. 📖 查看使用说明")
    print("  6. 🚪 退出")
    print()


def run_commandline_search():
    """运行命令行搜索"""
    print("\n🔍 命令行搜索")
    print("-" * 40)

    keyword = input("请输入搜索关键词: ").strip()
    if not keyword:
        print("❌ 关键词不能为空")
        return

    # 搜索方法选择
    print("\n选择搜索方法:")
    print("  1. Playwright (推荐，最稳定)")
    print("  2. API (直接请求，可能失效)")
    print("  3. DOM解析 (备用)")
    print("  4. 自动选择")

    method_choice = input("请选择 [默认1]: ").strip()
    method_map = {"1": "playwright", "2": "api", "3": "dom", "4": "auto", "": "playwright"}
    method = method_map.get(method_choice, "playwright")

    max_results = input("最大结果数量 [默认10]: ").strip()
    min_likes = input("最小点赞数 [默认0]: ").strip()

    # 构建命令
    cmd = ["python", "example_search.py", keyword, "--method", method]

    if max_results:
        cmd.extend(["-n", max_results])

    if min_likes:
        cmd.extend(["-l", min_likes])

    # Playwright特有选项
    if method == "playwright":
        headless_choice = input("使用无头模式(不显示浏览器)? (y/N): ").strip().lower()
        if headless_choice == 'y':
            cmd.append("--headless")

        scroll_times = input("滚动次数 [默认5]: ").strip()
        if scroll_times:
            cmd.extend(["--scroll-times", scroll_times])

    # 添加导出选项
    export_choice = input("是否导出结果? (y/N): ").strip().lower()
    if export_choice == 'y':
        format_choice = input("导出格式 (json/csv/both) [默认json]: ").strip()
        if format_choice:
            cmd.extend(["--export", format_choice])
        else:
            cmd.extend(["--export", "json"])

    # 添加下载选项
    download_choice = input("是否下载视频? (y/N): ").strip().lower()
    if download_choice == 'y':
        cmd.append("--download")
        download_dir = input("下载目录 [默认./downloads]: ").strip()
        if download_dir:
            cmd.extend(["--download-dir", download_dir])

    print(f"\n🚀 执行命令: {' '.join(cmd)}")
    print("-" * 40)

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 命令执行失败: {e}")
    except KeyboardInterrupt:
        print("\n⏹️  用户中断操作")
    except Exception as e:
        print(f"❌ 发生错误: {e}")


def run_web_interface():
    """启动Web界面"""
    print("\n🌐 启动Web界面")
    print("-" * 40)

    try:
        # 检查是否有Web应用
        from dy_video_download.app import app

        port = 5000
        url = f"http://localhost:{port}"

        print(f"🚀 启动Flask应用，端口: {port}")
        print(f"🌐 请在浏览器中访问: {url}")
        print("按 Ctrl+C 停止服务")

        # 在浏览器中打开
        webbrowser.open(url)

        # 运行应用
        app.run(debug=False, port=port)

    except ImportError:
        print("❌ 找不到Web应用")
        print("请确保 app.py 文件存在")
    except KeyboardInterrupt:
        print("\n⏹️  停止Web服务")
    except Exception as e:
        print(f"❌ 启动Web界面失败: {e}")


def run_tests():
    """运行测试"""
    print("\n🧪 运行功能测试")
    print("-" * 40)

    print("选择测试:")
    print("  1. 增强版搜索测试")
    print("  2. Playwright搜索测试")
    print("  3. 所有测试")

    test_choice = input("请选择 [默认1]: ").strip()

    test_scripts = {
        "1": "test_enhanced_search.py",
        "2": "test_playwright_search.py",  # 我们将创建这个
        "3": "test_all.py"  # 我们也将创建这个
    }

    script = test_scripts.get(test_choice, "test_enhanced_search.py")

    try:
        if script == "test_playwright_search.py" and not os.path.exists(script):
            # 创建简单的Playwright测试脚本
            create_playwright_test_script()

        subprocess.run(["python", script], check=True)
    except FileNotFoundError:
        print(f"❌ 找不到测试脚本: {script}")
    except subprocess.CalledProcessError as e:
        print(f"❌ 测试执行失败: {e}")
    except KeyboardInterrupt:
        print("\n⏹️  用户中断测试")
    except Exception as e:
        print(f"❌ 发生错误: {e}")

def create_playwright_test_script():
    """创建Playwright测试脚本"""
    content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Playwright搜索功能测试
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from dy_video_download.playwright_search import test_playwright_search
    import asyncio

    print("🧪 测试Playwright搜索功能")
    print("=" * 60)

    success = asyncio.run(test_playwright_search())

    if success:
        print("\\n✅ Playwright搜索测试通过")
        sys.exit(0)
    else:
        print("\\n❌ Playwright搜索测试失败")
        sys.exit(1)

except ImportError as e:
    print(f"❌ 导入Playwright模块失败: {e}")
    print("请先安装依赖:")
    print("  1. 运行 'python install_playwright.py'")
    print("  2. 或手动安装: pip install playwright && playwright install chromium")
    sys.exit(1)
except Exception as e:
    print(f"❌ 测试过程中出错: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''

    with open("test_playwright_search.py", "w", encoding="utf-8") as f:
        f.write(content)

    os.chmod("test_playwright_search.py", 0o755)
    print("✅ 已创建Playwright测试脚本")

def install_dependencies():
    """安装依赖"""
    print("\n🛠️  安装依赖")
    print("-" * 40)

    if not os.path.exists("install_playwright.py"):
        print("❌ 找不到安装脚本")
        print("请手动安装:")
        print("  pip install playwright requests beautifulsoup4")
        print("  playwright install chromium")
        return

    try:
        subprocess.run([sys.executable, "install_playwright.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 安装失败: {e}")
    except KeyboardInterrupt:
        print("\n⏹️  用户中断安装")
    except Exception as e:
        print(f"❌ 发生错误: {e}")


def show_usage():
    """显示使用说明"""
    print("\n📖 使用说明")
    print("-" * 40)

    try:
        with open("README_SEARCH.md", "r", encoding="utf-8") as f:
            content = f.read()

            # 提取关键部分
            sections = content.split("## ")
            for i, section in enumerate(sections):
                if i == 0:
                    continue  # 跳过标题

                lines = section.split("\n")
                title = lines[0]
                body = "\n".join(lines[1:4])  # 只显示前几行

                print(f"\n{title}:")
                print(f"  {body[:100]}...")

                if i >= 3:  # 只显示前3个部分
                    break

        print("\n📚 详细文档请查看 README_SEARCH.md 文件")

    except FileNotFoundError:
        print("❌ 找不到文档文件")
        print("基本使用方法:")
        print("  1. 搜索: python example_search.py <关键词>")
        print("  2. Web界面: python run.py")
        print("  3. 测试: python test_enhanced_search.py")


def main():
    """主函数"""
    print_banner()

    while True:
        print_menu()

        try:
            choice = input("请输入选项 (1-6): ").strip()

            if choice == "1":
                run_commandline_search()
            elif choice == "2":
                run_web_interface()
            elif choice == "3":
                run_tests()
            elif choice == "4":
                install_dependencies()
            elif choice == "5":
                show_usage()
            elif choice == "6":
                print("\n👋 再见！")
                break
            else:
                print("❌ 无效选项，请重新输入")

        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")

        print("\n" + "-" * 40)


if __name__ == "__main__":
    main()