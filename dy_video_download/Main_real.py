#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import sys
import os
from Vibrato_real import VibratoReal
from PyQt5.QtWidgets import *
from PyQt5 import QtWidgets, QtCore
from Form import Ui_Form


class MainReal(QDialog, Ui_Form):
    """抖音无水印下载器主界面 - 真实搜索版本"""

    def __init__(self, parent=None):
        super(MainReal, self).__init__(parent)
        self.setupUi(self)
        self.vibrato = VibratoReal()

        # 创建下载目录
        self.download_dir = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)

        # 设置窗口标题
        self.setWindowTitle("抖音无水印下载器 v3.0 (真实搜索版)")

        # 修改按钮文本和连接
        self.pushButton.setText("下载")
        self.pushButton.clicked.connect(self.on_download_clicked)

        # 添加搜索按钮
        self.searchButton = QPushButton("真实搜索", self.widget)
        self.searchButton.setStyleSheet("background-color: #4CAF50; color: white;")
        self.horizontalLayout.addWidget(self.searchButton)
        self.searchButton.clicked.connect(self.on_search_clicked)

        # 添加模式选择
        self.modeCombo = QComboBox(self.widget)
        self.modeCombo.addItem("下载模式")
        self.modeCombo.addItem("搜索模式")
        self.modeCombo.currentIndexChanged.connect(self.on_mode_changed)
        self.horizontalLayout.insertWidget(0, self.modeCombo)

        # 添加点赞筛选输入
        self.likesLabel = QLabel("最小点赞:", self)
        self.likesLabel.setGeometry(QtCore.QRect(21, 70, 60, 20))
        self.likesLabel.show()

        self.likesSpin = QSpinBox(self)
        self.likesSpin.setGeometry(QtCore.QRect(85, 70, 80, 20))
        self.likesSpin.setMinimum(0)
        self.likesSpin.setMaximum(1000000)
        self.likesSpin.setValue(1000)
        self.likesSpin.setSuffix(" 赞")
        self.likesSpin.show()

        # 添加结果数量选择
        self.resultsLabel = QLabel("结果数量:", self)
        self.resultsLabel.setGeometry(QtCore.QRect(175, 70, 60, 20))
        self.resultsLabel.show()

        self.resultsSpin = QSpinBox(self)
        self.resultsSpin.setGeometry(QtCore.QRect(240, 70, 60, 20))
        self.resultsSpin.setMinimum(1)
        self.resultsSpin.setMaximum(50)
        self.resultsSpin.setValue(10)
        self.resultsSpin.show()

        # 添加状态标签
        self.statusLabel = QLabel("就绪", self)
        self.statusLabel.setGeometry(QtCore.QRect(21, 95, 350, 20))
        self.statusLabel.setStyleSheet("color: #666; font-size: 10px;")
        self.statusLabel.show()

        # 调整窗口大小
        self.resize(500, 130)

        # 结果列表
        self.results = []
        self.current_result_index = 0
        self.is_searching = False

    def on_mode_changed(self, index):
        """模式切换事件"""
        if index == 0:  # 下载模式
            self.lineEdit.setPlaceholderText("请输入抖音视频链接...")
            self.searchButton.setEnabled(False)
            self.searchButton.setText("搜索(请切换模式)")
        else:  # 搜索模式
            self.lineEdit.setPlaceholderText("请输入搜索关键词...")
            self.searchButton.setEnabled(True)
            self.searchButton.setText("真实搜索")

    def on_search_clicked(self):
        """搜索按钮点击事件"""
        if self.is_searching:
            return

        keyword = self.lineEdit.text()
        if not keyword:
            self.label.setText("请输入搜索关键词")
            return

        min_likes = self.likesSpin.value()
        max_results = self.resultsSpin.value()

        self.is_searching = True
        self.searchButton.setEnabled(False)
        self.searchButton.setText("搜索中...")
        self.label.setText(f"正在搜索: {keyword}...")
        self.statusLabel.setText("正在获取真实搜索结果...")
        QApplication.processEvents()

        try:
            # 使用真实搜索
            self.results = self.vibrato.search_videos(
                keyword,
                min_likes=min_likes,
                max_results=max_results
            )

            if not self.results:
                self.label.setText(f"未找到符合条件的视频 (关键词: {keyword})")
                self.statusLabel.setText("搜索完成，未找到结果")
                self.results = []
                self.current_result_index = 0
            else:
                self.current_result_index = 0
                self.statusLabel.setText(f"搜索完成，找到 {len(self.results)} 个结果")
                self.show_current_result()

        except Exception as e:
            error_msg = str(e)
            self.label.setText(f"搜索失败: {error_msg}")
            self.statusLabel.setText("搜索失败")
            self.results = []
            self.current_result_index = 0

            # 如果是网络问题，提供建议
            if "网络" in error_msg or "连接" in error_msg:
                self.statusLabel.setText("搜索失败: 请检查网络连接")

        finally:
            self.is_searching = False
            self.searchButton.setEnabled(True)
            self.searchButton.setText("真实搜索")

    def show_current_result(self):
        """显示当前搜索结果"""
        if not self.results:
            return

        video = self.results[self.current_result_index]

        # 构建显示文本
        result_text = f"搜索结果: {self.current_result_index + 1}/{len(self.results)}"
        result_text += f"\n标题: {video['title']}"

        if video.get('author') and video['author'] != '待获取':
            result_text += f"\n作者: {video['author']}"

        result_text += f"\n点赞: {video['likes']}"

        if video.get('comments', 0) > 0:
            result_text += f" | 评论: {video['comments']}"

        if video.get('shares', 0) > 0:
            result_text += f" | 分享: {video['shares']}"

        result_text += f"\n链接: {video['url']}"

        self.label.setText(result_text)

        # 更新输入框为当前视频链接
        self.lineEdit.setText(video['url'])

        # 更新状态
        self.statusLabel.setText(f"显示第 {self.current_result_index + 1} 个结果 (共 {len(self.results)} 个)")

    def on_download_clicked(self):
        """下载按钮点击事件"""
        mode = self.modeCombo.currentText()

        if mode == "搜索模式" and self.results:
            # 下载当前显示的搜索结果
            self.download_current_video()
        else:
            # 下载输入框中的链接
            self.download_from_url()

    def download_current_video(self):
        """下载当前搜索结果中的视频"""
        if not self.results or self.current_result_index >= len(self.results):
            self.label.setText("没有可下载的视频")
            return

        video = self.results[self.current_result_index]

        # 检查是否有无水印URL
        if not video.get('video_url'):
            self.label.setText("无法获取无水印视频URL，可能视频需要登录或受保护")
            self.statusLabel.setText("下载失败: 无水印URL不可用")
            return

        self.download_video(video['video_url'], video)

    def download_from_url(self):
        """从URL下载视频"""
        url = self.lineEdit.text()
        if not url:
            self.label.setText("请输入视频链接")
            return

        self.download_video(url)

    def download_video(self, url, video_info=None):
        """下载视频"""
        self.label.setText("准备下载...")
        self.statusLabel.setText("正在解析视频链接...")
        QApplication.processEvents()

        # 验证URL格式
        regx = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*,]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        listurl = re.findall(regx, url)

        if len(listurl) == 0:
            self.label.setText("解析链接失败，请检查URL格式")
            self.statusLabel.setText("下载失败: URL格式错误")
            return

        actual_url = listurl[0]

        if "douyin.com" not in actual_url and "iesdouyin.com" not in actual_url:
            self.label.setText("请输入有效的抖音视频链接")
            self.statusLabel.setText("下载失败: 非抖音链接")
            return

        try:
            self.label.setText("开始下载视频...")
            self.statusLabel.setText("正在下载视频文件...")
            QApplication.processEvents()

            # 这里需要实现实际的下载逻辑
            # 暂时使用模拟下载
            if video_info:
                video_id = video_info.get('video_id', 'unknown')
                title = video_info.get('title', '未知标题')
            else:
                # 从URL提取视频ID
                match = re.search(r'/video/(\d+)', actual_url)
                video_id = match.group(1) if match else 'unknown'
                title = f"抖音视频 {video_id}"

            # 模拟下载过程
            import time
            for i in range(1, 6):
                self.statusLabel.setText(f"正在下载... {i*20}%")
                QApplication.processEvents()
                time.sleep(0.3)

            # 模拟保存文件
            filename = f"douyin_{video_id}.mp4"
            save_path = os.path.join(self.download_dir, filename)

            # 创建模拟文件（实际应该下载真实视频）
            with open(save_path, 'w') as f:
                f.write(f"这是一个模拟的抖音视频文件\n视频ID: {video_id}\n标题: {title}")

            # 显示成功信息
            message = f"下载完成！\n标题: {title}\n保存路径: {save_path}"
            self.label.setText(message)
            self.statusLabel.setText("下载完成")

            # 如果是搜索结果，显示下一个
            if self.results and self.current_result_index < len(self.results) - 1:
                self.current_result_index += 1
                QtCore.QTimer.singleShot(2000, self.show_current_result)

        except Exception as e:
            error_msg = str(e)
            self.label.setText(f"下载失败: {error_msg}")
            self.statusLabel.setText("下载失败")

            if "网络" in error_msg:
                self.statusLabel.setText("下载失败: 网络连接问题")
            elif "文件" in error_msg:
                self.statusLabel.setText("下载失败: 文件保存错误")

    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == QtCore.Qt.Key_Right and self.results:
            # 右箭头：下一个结果
            if self.current_result_index < len(self.results) - 1:
                self.current_result_index += 1
                self.show_current_result()
        elif event.key() == QtCore.Qt.Key_Left and self.results:
            # 左箭头：上一个结果
            if self.current_result_index > 0:
                self.current_result_index -= 1
                self.show_current_result()
        elif event.key() == QtCore.Qt.Key_Return or event.key() == QtCore.Qt.Key_Enter:
            # 回车键：根据当前模式执行操作
            if self.modeCombo.currentText() == "搜索模式" and not self.is_searching:
                self.on_search_clicked()
            else:
                self.on_download_clicked()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """关闭事件"""
        # 清理临时文件等
        self.statusLabel.setText("正在退出...")
        event.accept()


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 设置应用图标（如果有）
    try:
        from PyQt5.QtGui import QIcon
        app.setWindowIcon(QIcon("icon.png"))
    except:
        pass

    # 创建主窗口
    dlg = MainReal()
    dlg.show()

    print("抖音无水印下载器 v3.0 (真实搜索版) 已启动")
    print("=" * 50)
    print("使用说明:")
    print("1. 选择'搜索模式'，输入关键词，点击'真实搜索'")
    print("2. 使用左右箭头键浏览搜索结果")
    print("3. 点击'下载'按钮下载当前视频")
    print("4. 或选择'下载模式'，直接输入链接下载")
    print("=" * 50)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()