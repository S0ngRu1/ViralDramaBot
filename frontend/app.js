/**
 * ViralDramaBot - Vue 3 Frontend Application
 * 
 * 主要功能：
 * - 下载视频表单
 * - 视频管理列表
 * - 应用设置
 * - 完整的短剧处理流程
 */

const { createApp, ref, reactive, computed, onMounted } = Vue;

// ============================================================================
// API 客户端
// ============================================================================

const API_BASE_URL = "http://localhost:8000/api";

const api = {
    /**
     * 下载视频
     */
    downloadVideo: async (link) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/videos/download`, {
                link: link
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    /**
     * 获取视频列表
     */
    getVideos: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/videos`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    /**
     * 获取视频详情
     */
    getVideoDetail: async (videoId) => {
        try {
            const response = await axios.get(`${API_BASE_URL}/videos/${videoId}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    /**
     * 删除视频
     */
    deleteVideo: async (videoId) => {
        try {
            const response = await axios.delete(`${API_BASE_URL}/videos/${videoId}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    /**
     * 获取下载进度
     */
    getDownloadProgress: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/download-progress`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    /**
     * 获取应用设置
     */
    getSettings: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/settings`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    /**
     * 更新应用设置
     */
    updateSettings: async (settings) => {
        try {
            const response = await axios.put(`${API_BASE_URL}/settings`, settings);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    /**
     * 获取应用状态
     */
    getStatus: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/status`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    }
};

// ============================================================================
// Vue 应用
// ============================================================================

const app = createApp({
    template: `
        <div class="container">
            <!-- 侧边栏 -->
            <div class="sidebar">
                <div class="sidebar-logo">
                    <span>🎬 ViralDramaBot</span>
                </div>
                <ul class="sidebar-menu">
                    <li>
                        <a 
                            :class="{ active: currentPage === 'download' }"
                            @click="currentPage = 'download'"
                        >
                            📥 视频下载
                        </a>
                    </li>
                    <li>
                        <a 
                            :class="{ active: currentPage === 'videos' }"
                            @click="currentPage = 'videos'"
                        >
                            📺 视频管理
                        </a>
                    </li>
                    <li>
                        <a 
                            :class="{ active: currentPage === 'settings' }"
                            @click="currentPage = 'settings'"
                        >
                            ⚙️ 应用设置
                        </a>
                    </li>
                </ul>
            </div>

            <!-- 主内容区域 -->
            <div class="main-content">
                <!-- 下载页面 -->
                <div v-if="currentPage === 'download'">
                    <download-page 
                        :api="api"
                        :settings="settings"
                        @download="handleDownload"
                    />
                </div>

                <!-- 视频管理页面 -->
                <div v-if="currentPage === 'videos'">
                    <videos-page 
                        :api="api"
                        :videos="videos"
                        @reload="loadVideos"
                    />
                </div>

                <!-- 设置页面 -->
                <div v-if="currentPage === 'settings'">
                    <settings-page 
                        :api="api"
                        :settings="settings"
                        @save="handleSaveSettings"
                    />
                </div>
            </div>
        </div>
    `,

    setup() {
        const currentPage = ref('download');
        const videos = ref([]);
        const settings = ref({
            video_dir: '.data',
            download_timeout: 60,
            max_retries: 3
        });
        const messages = ref([]);

        // 加载视频列表
        const loadVideos = async () => {
            try {
                const result = await api.getVideos();
                videos.value = result.videos || [];
            } catch (error) {
                showMessage('❌ 加载视频列表失败', 'danger');
                console.error(error);
            }
        };

        // 加载设置
        const loadSettings = async () => {
            try {
                const result = await api.getSettings();
                settings.value = result.settings;
                // 更新下载页的保存路径
                if (currentPage.value === 'download') {
                    // 通过事件总线或其他方式更新
                }
            } catch (error) {
                showMessage('❌ 加载设置失败', 'danger');
                console.error(error);
            }
        };

        // 显示消息
        const showMessage = (message, type = 'info') => {
            const id = Date.now();
            messages.value.push({ id, message, type });
            setTimeout(() => {
                messages.value = messages.value.filter(m => m.id !== id);
            }, 3000);
        };

        // 处理下载
        const handleDownload = async (link) => {
            try {
                showMessage('✅ 下载已启动，请稍候...', 'success');
                await api.downloadVideo(link);
                
                // 等待 5 秒后刷新视频列表
                setTimeout(() => {
                    loadVideos();
                }, 5000);
            } catch (error) {
                showMessage(`❌ 下载失败: ${error.message || error}`, 'danger');
            }
        };

        // 处理保存设置
        const handleSaveSettings = async (newSettings) => {
            try {
                await api.updateSettings(newSettings);
                settings.value = newSettings;
                showMessage('✅ 设置已保存', 'success');
            } catch (error) {
                showMessage(`❌ 保存设置失败: ${error.message || error}`, 'danger');
            }
        };

        // 页面加载时初始化
        onMounted(() => {
            loadVideos();
            loadSettings();
        });

        return {
            currentPage,
            videos,
            settings,
            messages,
            api,
            loadVideos,
            loadSettings,
            showMessage,
            handleDownload,
            handleSaveSettings
        };
    }
});

// ============================================================================
// 下载页面组件
// ============================================================================

app.component('download-page', {
    props: ['api', 'settings'],
    emits: ['download'],
    template: `
        <div>
            <div class="header">
                <h1>📥 视频下载</h1>
                <p>输入抖音分享链接，一键下载无水印视频</p>
            </div>

            <div class="card">
                <div class="card-title">下载视频</div>
                
                <div class="form-group">
                    <label>抖音分享链接 *</label>
                    <input 
                        v-model="link"
                        type="url"
                        placeholder="输入抖音视频分享链接，如: https://v.douyin.com/7PkMlgCQjjY/"
                        @keyup.enter="submit"
                    />
                </div>

                <div class="form-group">
                    <label>保存目录</label>
                    <input 
                        v-model="savePath"
                        type="text"
                        placeholder="视频保存目录，默认为 .data"
                    />
                </div>

                <div class="row">
                    <button 
                        class="btn btn-primary btn-block"
                        @click="submit"
                        :disabled="!link || isLoading"
                    >
                        <span v-if="!isLoading">🚀 开始下载</span>
                        <span v-else>
                            <div class="spinner" style="width: 16px; height: 16px; border-width: 2px;"></div>
                            下载中...
                        </span>
                    </button>
                </div>
            </div>

            <!-- 下载进度 - 一开始就显示 -->
            <div v-if="isLoading || progress.status !== 'idle'" class="card">
                <div class="card-title">📊 下载进度</div>
                <div class="progress">
                    <div 
                        class="progress-bar"
                        :style="{ width: progress.percentage + '%' }"
                    ></div>
                </div>
                <div class="progress-text">
                    {{ progress.percentage.toFixed(1) }}% - {{ formatBytes(progress.downloaded) }} / {{ formatBytes(progress.total) }}
                </div>
                <p class="mt-2" :class="{'text-success': progress.status === 'completed', 'text-danger': progress.status === 'error'}">
                    {{ progress.message }}
                </p>
            </div>

            <!-- 提示 -->
            <div class="card">
                <div class="card-title">💡 使用提示</div>
                <ul style="margin-left: 20px;">
                    <li>支持抖音短链接（v.douyin.com）和长链接</li>
                    <li>自动获取无水印版本</li>
                    <li>支持最长 20 分钟的短视频下载</li>
                    <li>下载时间取决于网络速度和文件大小</li>
                    <li>视频默认保存到 <code>.data</code> 目录，可在上方自定义</li>
                </ul>
            </div>
        </div>
    `,

    setup(props, { emit }) {
        const link = ref('');
        const savePath = ref('');
        const isLoading = ref(false);
        const progress = ref({
            status: 'idle',
            percentage: 0,
            downloaded: 0,
            total: 0,
            message: '就绪'
        });

        // 定时更新进度
        let progressInterval = null;

        const submit = async () => {
            if (!link.value) return;

            isLoading.value = true;
            try {
                emit('download', link.value);
                link.value = '';

                // 启动进度监测
                if (progressInterval) clearInterval(progressInterval);
                progressInterval = setInterval(async () => {
                    try {
                        const result = await props.api.getDownloadProgress();
                        progress.value = result;
                        
                        if (result.status === 'completed' || result.status === 'error') {
                            clearInterval(progressInterval);
                            isLoading.value = false;
                        }
                    } catch (error) {
                        console.error('获取进度失败', error);
                    }
                }, 1000);
            } catch (error) {
                isLoading.value = false;
                console.error(error);
            }
        };

        const formatBytes = (bytes) => {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        };

        return {
            link,
            savePath,
            isLoading,
            progress,
            submit,
            formatBytes
        };
    }
});

// ============================================================================
// 视频管理页面组件
// ============================================================================

app.component('videos-page', {
    props: ['api', 'videos'],
    emits: ['reload'],
    template: `
        <div>
            <div class="header flex-between">
                <div>
                    <h1>📺 视频管理</h1>
                    <p>已下载 {{ videos.length }} 个视频</p>
                </div>
                <button class="btn btn-primary" @click="reload">
                    🔄 刷新
                </button>
            </div>

            <div v-if="videos.length === 0" class="card text-center">
                <p style="padding: 40px 0; color: #999;">
                    还没有下载过视频 <br/>
                    去<a href="#" @click.prevent="$parent.currentPage = 'download'">视频下载</a>开始吧
                </p>
            </div>

            <div v-else>
                <table class="table">
                    <thead>
                        <tr>
                            <th>视频 ID</th>
                            <th>标题</th>
                            <th>文件大小</th>
                            <th>创建时间</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="video in videos" :key="video.video_id">
                            <td><code style="background: #f5f5f5; padding: 2px 6px; border-radius: 3px;">{{ video.video_id }}</code></td>
                            <td class="truncate" :title="video.title">{{ video.title }}</td>
                            <td>{{ formatBytes(video.file_size) }}</td>
                            <td>{{ formatDate(video.created_at) }}</td>
                            <td>
                                <button 
                                    class="btn btn-danger btn-small"
                                    @click="deleteVideo(video.video_id)"
                                >
                                    🗑️ 删除
                                </button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    `,

    setup(props, { emit }) {
        const reload = () => {
            emit('reload');
        };

        const deleteVideo = async (videoId) => {
            if (confirm('确定要删除这个视频吗？')) {
                try {
                    await props.api.deleteVideo(videoId);
                    reload();
                    alert('✅ 视频已删除');
                } catch (error) {
                    alert('❌ 删除失败: ' + (error.message || error));
                }
            }
        };

        const formatBytes = (bytes) => {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        };

        const formatDate = (dateString) => {
            try {
                const date = new Date(parseFloat(dateString) * 1000);
                return date.toLocaleString('zh-CN');
            } catch {
                return dateString;
            }
        };

        return {
            reload,
            deleteVideo,
            formatBytes,
            formatDate
        };
    }
});

// ============================================================================
// 设置页面组件
// ============================================================================

app.component('settings-page', {
    props: ['api', 'settings'],
    emits: ['save'],
    template: `
        <div>
            <div class="header">
                <h1>⚙️ 应用设置</h1>
                <p>配置 ViralDramaBot 的运行参数</p>
            </div>

            <div class="card">
                <div class="card-title">基本设置</div>

                <div class="form-group">
                    <label>视频保存目录</label>
                    <input 
                        v-model="formData.video_dir"
                        type="text"
                        placeholder="输入视频保存目录，如: .data 或 /home/user/videos"
                    />
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        默认值: .data
                    </p>
                </div>

                <div class="form-group">
                    <label>下载超时时间 (秒)</label>
                    <input 
                        v-model.number="formData.download_timeout"
                        type="number"
                        min="10"
                        max="300"
                    />
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        单次下载操作的最大超时时间，适当增加可支持更大文件下载
                    </p>
                </div>

                <div class="form-group">
                    <label>最大重试次数</label>
                    <input 
                        v-model.number="formData.max_retries"
                        type="number"
                        min="1"
                        max="10"
                    />
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        网络请求失败时的重试次数
                    </p>
                </div>

                <button 
                    class="btn btn-primary btn-block"
                    @click="save"
                >
                    💾 保存设置
                </button>
            </div>

            <!-- 系统信息 -->
            <div class="card">
                <div class="card-title">系统信息</div>
                <div class="row">
                    <div class="col">
                        <div>
                            <strong>应用名称:</strong><br/>
                            ViralDramaBot
                        </div>
                    </div>
                    <div class="col">
                        <div>
                            <strong>版本:</strong><br/>
                            0.1.0
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,

    setup(props, { emit }) {
        const formData = reactive({
            video_dir: props.settings.video_dir,
            download_timeout: props.settings.download_timeout,
            max_retries: props.settings.max_retries
        });

        const save = async () => {
            try {
                emit('save', formData);
            } catch (error) {
                alert('❌ 保存失败: ' + (error.message || error));
            }
        };

        return {
            formData,
            save
        };
    }
});

// ============================================================================
// 挂载应用
// ============================================================================

app.mount('#app');
