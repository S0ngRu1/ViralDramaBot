#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
抖音无水印视频下载器 - 启动脚本

功能：
1. 检查依赖
2. 创建必要目录
3. 启动主程序
"""

import sys
import os
import subprocess

def check_dependencies():
    """检查必要的依赖包"""
    print("检查依赖包...")

    dependencies = ["requests", "PyQt5"]
    missing = []

    for dep in dependencies:
        try:
            __import__(dep.split('.')[0])
            print(f"✓ {dep}")
        except ImportError:
            print(f"✗ {dep}")
            missing.append(dep)

    if missing:
        print(f"\n缺少依赖包: {', '.join(missing)}")
        print("请使用以下命令安装:")
        print(f"pip install {' '.join(missing)}")
        return False

    print("所有依赖包已安装")
    return True

def create_directories():
    """创建必要的目录"""
    print("\n创建目录结构...")

    directories = ["downloads", ".data"]

    for dir_name in directories:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"✓ 创建目录: {dir_name}")
        else:
            print(f"✓ 目录已存在: {dir_name}")

    return True

def check_python_version():
    """检查Python版本"""
    print("\n检查Python版本...")

    version = sys.version_info
    print(f"当前Python版本: {version.major}.{version.minor}.{version.micro}")

    if version.major >= 3 and version.minor >= 7:
        print("✓ Python版本符合要求")
        return True
    else:
        print("✗ 需要Python 3.7或更高版本")
        return False

def start_main_program():
    """启动主程序"""
    print("\n启动抖音下载器...")
    print("=" * 50)

    try:
        # 导入并运行主程序
        from Main import Main
        from PyQt5.QtWidgets import QApplication

        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        window = Main()
        window.show()

        print("程序已启动！")
        print("使用说明:")
        print("1. 选择搜索模式或下载模式")
        print("2. 输入关键词或视频链接")
        print("3. 点击相应按钮执行操作")
        print("4. 使用左右箭头键浏览搜索结果")

        return app.exec_()

    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

def show_help():
    """显示帮助信息"""
    print("""
抖音无水印视频下载器 - 启动脚本

使用方法:
    python start.py          启动图形界面
    python start.py test     运行功能测试
    python start.py help     显示此帮助信息

功能特点:
    1. 关键词搜索抖音视频
    2. 按点赞数筛选结果
    3. 无水印视频下载
    4. 用户友好的图形界面

目录结构:
    downloads/     视频下载目录
    .data/         临时数据目录

更多帮助请查看 USAGE.md
    """)

def run_tests():
    """运行功能测试"""
    print("运行功能测试...")

    try:
        # 运行测试脚本
        result = subprocess.run(
            [sys.executable, "test_final.py"],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)

        return result.returncode == 0

    except Exception as e:
        print(f"测试运行失败: {e}")
        return False

def main():
    """主函数"""
    print("抖音无水印视频下载器 v2.0")
    print("=" * 50)

    # 解析命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "help" or command == "-h" or command == "--help":
            show_help()
            return 0
        elif command == "test":
            if check_python_version() and check_dependencies():
                create_directories()
                return 0 if run_tests() else 1
            return 1
        else:
            print(f"未知命令: {command}")
            show_help()
            return 1

    # 正常启动流程
    if not check_python_version():
        return 1

    if not check_dependencies():
        print("\n请先安装缺失的依赖包，然后重新启动。")
        return 1

    if not create_directories():
        return 1

    # 启动主程序
    return start_main_program()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)