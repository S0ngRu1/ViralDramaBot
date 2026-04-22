#!/usr/bin/python
# -*- coding: utf-8 -*-
# pyuic5 form.ui -o form.py

import re
import sys
import os
from Vibrato import Vibrato
from PyQt5.QtWidgets import *
from PyQt5 import QtWidgets, QtGui, QtCore
from Form import Ui_Form


class Main(QDialog, Ui_Form):
    """抖音无水印下载器主界面"""
    def __init__(self, parent=None):
        super(Main, self).__init__(parent)
        self.setupUi(self)
        self.vibrato = Vibrato()

        # 创建下载目录
        self.download_dir = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)

        # 设置窗口标题
        self.setWindowTitle("抖音无水印下载器 v2.0")

        # 修改按钮文本和连接
        self.pushButton.setText("下载")
        self.pushButton.clicked.connect(self.on_download_clicked)

        # 添加搜索按钮
        self.searchButton = QPushButton("搜索", self.widget)
        self.horizontalLayout.addWidget(self.searchButton)
        self.searchButton.clicked.connect(self.on_search_clicked)

        # 添加模式选择
        self.modeCombo = QComboBox(self.widget)
        self.modeCombo.addItem("下载模式")
        self.modeCombo.addItem("搜索模式")
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

        # 调整窗口大小
        self.resize(500, 150)

        # 结果列表
        self.results = []
        self.current_result_index = 0

    def on_search_clicked(self):
        """搜索按钮点击事件"""
        self.label.setText("搜索中，请稍等...")
        QApplication.processEvents()

        keyword = self.lineEdit.text()
        if not keyword:
            self.label.setText("请输入搜索关键词")
            return

        min_likes = self.likesSpin.value()

        try:
            self.results = self.vibrato.search_videos(keyword, min_likes=min_likes)

            if not self.results:
                self.label.setText("未找到符合条件的视频")
                self.results = []
                self.current_result_index = 0
            else:
                self.current_result_index = 0
                self.show_current_result()

        except Exception as e:
            self.label.setText(f"搜索失败: {str(e)}")

    def show_current_result(self):
        """显示当前搜索结果"""
        if not self.results:
            return

        video = self.results[self.current_result_index]
        result_text = f"找到 {len(self.results)} 个视频 | 当前: {self.current_result_index + 1}/{len(self.results)}"
        result_text += f"\n标题: {video['title']}"
        result_text += f"\n点赞: {video['likes']}"
        result_text += f"\n链接: {video['url']}"

        self.label.setText(result_text)

        # 更新输入框为当前视频链接
        self.lineEdit.setText(video['url'])

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
        url = video['url']

        self.download_video(url)

    def download_from_url(self):
        """从URL下载视频"""
        url = self.lineEdit.text()
        if not url:
            self.label.setText("请输入视频链接")
            return

        self.download_video(url)

    def download_video(self, url):
        """下载视频"""
        self.label.setText("解析链接中...")
        QApplication.processEvents()

        # 验证URL格式
        regx = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*,]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        listurl = re.findall(regx, url)

        if len(listurl) == 0:
            self.label.setText("解析链接失败，请检查URL格式")
            return

        actual_url = listurl[0]

        if "douyin.com" not in actual_url and "iesdouyin.com" not in actual_url:
            self.label.setText("请输入有效的抖音视频链接")
            return

        try:
            self.label.setText("开始下载视频...")
            QApplication.processEvents()

            result = self.vibrato.run(actual_url)

            if result.get("status") == "success":
                save_path = result.get("save_path", "")
                title = result.get("title", "")
                likes = result.get("likes", 0)

                # 显示成功信息
                message = f"下载完成！\n标题: {title}\n点赞: {likes}\n保存路径: {save_path}"
                self.label.setText(message)

                # 如果是搜索结果，显示下一个
                if self.results and self.current_result_index < len(self.results) - 1:
                    self.current_result_index += 1
                    QtCore.QTimer.singleShot(2000, self.show_current_result)
            else:
                self.label.setText(f"下载失败: {result.get('message', '未知错误')}")

        except Exception as e:
            error_msg = str(e)
            if "无法获取视频信息" in error_msg:
                error_msg = "无法获取视频信息，链接可能已失效或需要登录"
            elif "无法获取无水印视频URL" in error_msg:
                error_msg = "无法获取无水印视频，可能视频受保护"
            elif "下载失败" in error_msg:
                error_msg = "视频下载失败，请检查网络连接"

            self.label.setText(f"下载失败: {error_msg}")

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
            if self.modeCombo.currentText() == "搜索模式":
                self.on_search_clicked()
            else:
                self.on_download_clicked()
        else:
            super().keyPressEvent(event)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 创建主窗口
    dlg = Main()
    dlg.show()

    sys.exit(app.exec_())
