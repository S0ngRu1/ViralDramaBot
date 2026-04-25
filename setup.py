"""
ViralDramaBot 安装配置
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() 
        for line in fh 
        if line.strip() 
        and not line.strip().startswith("#")
        and not line.strip().startswith("# ====")
    ]

setup(
    name="ViralDramaBot",
    version="0.1.0",
    author="Your Name",
    author_email="your-email@example.com",
    description="一站式短剧自动化流水线：从资源采集、智能剪辑到多平台矩阵发布的全链路解决方案",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/ViralDramaBot",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Development Status :: 3 - Alpha",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "viraldramabot=cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml"],
    },
)
