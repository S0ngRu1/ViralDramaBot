#!/bin/bash
set -e

echo "🧹 清理旧的输出目录..."
rm -rf dist/       # 删除目录模式输出（如果有）

echo "📦 Docker 打包..."
docker run --rm -v "$(pwd):/opt/src" tobix/pywine sh -c ' \
    wine pip install -r /opt/src/requirements.txt && \
    wine pip install pyinstaller && \
    export PYTHONPATH=$PYTHONPATH:/opt/src && \
    wine pyinstaller --clean \
        --distpath Z:\\opt\\src\\dist \
        /opt/src/ViralDramaBot.spec'

echo "✅ 打包完成！"