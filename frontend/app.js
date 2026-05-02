/**
 * ViralDramaBot - Vue 3 Frontend Application
 * 
 * 主要功能：
 * - 下载视频表单
 * - 视频管理列表
 * - 应用设置
 * - 完整的短剧处理流程
 */

const { createApp, ref, reactive, computed, onMounted, onBeforeUnmount, watch } = Vue;

// ============================================================================
// API 客户端
// ============================================================================

const API_BASE_URL = "http://localhost:8000/api";
const DOWNLOAD_SAVE_PATH_KEY = "viraldramabot.download.savePath";
const MAX_BATCH_ITEMS = 50;

const api = {
    /**
     * 下载视频
     */
    downloadVideo: async (tasks, savePath) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/videos/download`, {
                tasks: tasks,
                save_path: savePath || undefined
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

    batchDeleteVideos: async (videoIds) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/videos/batch-delete`, {
                video_ids: videoIds
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    openVideo: async (videoId) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/videos/${videoId}/open`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    openVideoFolder: async (videoId) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/videos/${videoId}/open-folder`);
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
     * 浏览本地目录
     */
    browseDirectory: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/browse-directory`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    /**
     * 解析视频信息
     */
    parseVideoInfo: async (link) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/videos/parse`, {
                link: link
            });
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
    },

    // ========================================================================
    // 微信视频号 API
    // ========================================================================

    getWeixinAccounts: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/weixin/accounts`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    createWeixinAccount: async (name) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/accounts`, { name });
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    loginWeixinAccount: async (id) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/accounts/${id}/login`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    refreshWeixinAccount: async (id) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/accounts/${id}/refresh`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    deleteWeixinAccount: async (id) => {
        try {
            const response = await axios.delete(`${API_BASE_URL}/weixin/accounts/${id}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    getWeixinTasks: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/weixin/tasks`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    createWeixinUpload: async (payload) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/upload`, payload);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    createWeixinBatchUpload: async (payload) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/upload/batch`, payload);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    retryWeixinTask: async (id) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/tasks/${id}/retry`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    deleteWeixinTask: async (id) => {
        try {
            const response = await axios.delete(`${API_BASE_URL}/weixin/tasks/${id}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    getWeixinSchedules: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/weixin/schedule`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    createWeixinSchedule: async (payload) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/schedule`, payload);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    deleteWeixinSchedule: async (id) => {
        try {
            const response = await axios.delete(`${API_BASE_URL}/weixin/schedule/${id}`);
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
                    <li>
                        <a
                            :class="{ active: currentPage === 'weixin' }"
                            @click="currentPage = 'weixin'"
                        >
                            📤 视频号上传
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
                        @completed="handleDownloadCompleted"
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

                <!-- 微信视频号上传页面 -->
                <div v-if="currentPage === 'weixin'">
                    <weixin-page :api="api" />
                </div>
            </div>
        </div>
    `,

    setup() {
        const currentPage = ref('download');
        const videos = ref([]);
        const settings = ref({
            video_dir: '.data',
            download_timeout: 1200,
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

        const handleDownloadCompleted = () => {
            loadVideos();
            showMessage('✅ 视频下载完成，已刷新视频列表', 'success');
        };

        // 处理保存设置
        const handleSaveSettings = async (newSettings) => {
            try {
                const result = await api.updateSettings(newSettings);
                settings.value = result.settings;
                localStorage.setItem(DOWNLOAD_SAVE_PATH_KEY, result.settings.video_dir);
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
            handleDownloadCompleted,
            handleSaveSettings
        };
    }
});

// ============================================================================
// 下载页面组件
// ============================================================================

app.component('download-page', {
    props: ['api', 'settings'],
    emits: ['completed'],
    template: `
        <div>
            <div class="header">
                <h1>📥 视频下载</h1>
                <p>输入抖音分享链接，支持下载约 20 分钟内的视频并实时查看保存进度</p>
            </div>

            <div class="card">
                <div class="card-title">下载视频</div>
                
                <div class="form-group">
                    <table class="table" style="margin-bottom: 10px;">
                        <thead>
                            <tr>
                                <th style="width: 58%;">视频链接</th>
                                <th style="width: 36%;">视频名称</th>
                                <th style="width: 6%;">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(item, idx) in downloadItems" :key="item.id">
                                <td>
                                    <input
                                        v-model="item.link"
                                        type="text"
                                        placeholder="https://v.douyin.com/xxxxx/"
                                    />
                                </td>
                                <td>
                                    <div class="row" style="margin-bottom: 0; align-items: flex-end; gap: 8px; flex-wrap: nowrap;">
                                        <div style="flex: 1; min-width: 0;">
                                            <input
                                                v-model="item.file_name"
                                                type="text"
                                                placeholder="留空则自动用视频标题"
                                                @blur="normalizeItemName(item)"
                                            />
                                        </div>
                                        <div style="display: flex; align-items: end;">
                                            <button
                                                class="btn btn-secondary btn-small task-action-btn"
                                                @click="hydrateItemName(idx)"
                                                :disabled="isLoading || item.isParsing || !item.link.trim()"
                                            >
                                                <span v-if="!item.isParsing">识别</span>
                                                <span v-else>识别中</span>
                                            </button>
                                        </div>
                                    </div>
                                </td>
                                <td style="vertical-align: bottom; text-align: left; padding-left: 6px; padding-right: 6px;">
                                    <button
                                        class="btn btn-secondary btn-small task-action-btn"
                                        @click="removeItem(idx)"
                                        :disabled="isLoading || downloadItems.length <= 1"
                                        title="删除当前行"
                                    >
                                        删除
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    <div class="row">
                        <button class="btn btn-secondary" @click="addItem" :disabled="isLoading || downloadItems.length >= MAX_BATCH_ITEMS">➕ 添加一行</button>
                        <button class="btn btn-secondary" @click="hydrateAllItemNames" :disabled="isLoading || validItems.length === 0 || isBatchParsing">
                            <span v-if="!isBatchParsing">✨ 全部自动识别</span>
                            <span v-else>识别中...</span>
                        </button>
                    </div>
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        当前有效链接 {{ validItems.length }} / {{ MAX_BATCH_ITEMS }} 个
                    </p>
                </div>

                <div class="form-group">
                    <label>保存目录</label>
                    <div class="row">
                        <div class="col">
                            <input 
                                :value="savePath"
                                type="text"
                                placeholder="请选择视频保存目录"
                                readonly
                            />
                        </div>
                        <div style="display: flex; align-items: end;">
                            <button
                                class="btn btn-secondary"
                                @click="browseSavePath"
                                :disabled="isLoading || isBrowsing"
                            >
                                <span v-if="!isBrowsing">📁 浏览</span>
                                <span v-else>选择中...</span>
                            </button>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <button 
                        class="btn btn-primary btn-block"
                        @click="submit"
                        :disabled="validItems.length === 0 || isLoading"
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
                        :style="{ width: realtimePercentage + '%' }"
                    ></div>
                </div>
                <div class="progress-text">
                    {{ realtimePercentage.toFixed(1) }}% - {{ formatBytes(progress.downloaded) }} / {{ formatBytes(progress.total) }}
                </div>
                <p class="mt-2"><strong>保存路径：</strong>{{ progress.file_path || savePath || settings.video_dir }}</p>
                <p class="mt-2" :class="{'text-success': progress.status === 'completed', 'text-danger': progress.status === 'error'}">
                    {{ progress.message }}
                </p>
            </div>

            <!-- 提示 -->
            <div class="card">
                <div class="card-title">💡 使用提示</div>
                <ul style="margin-left: 20px;">
                    <li>支持抖音短链接和长链接</li>
                    <li>自动获取无水印版本</li>
                    <li>下载时间取决于网络速度和文件大小，较大文件建议耐心等待</li>
                </ul>
            </div>
        </div>
    `,

    setup(props, { emit }) {
        const createEmptyItem = () => ({
            id: `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
            link: '',
            file_name: '',
            isParsing: false
        });
        const downloadItems = ref([createEmptyItem()]);
        const savePath = ref(localStorage.getItem(DOWNLOAD_SAVE_PATH_KEY) || props.settings.video_dir || '.data');
        const isLoading = ref(false);
        const isBrowsing = ref(false);
        const isBatchParsing = ref(false);
        const currentTaskStarted = ref(false);
        const progress = ref({
            status: 'idle',
            percentage: 0,
            downloaded: 0,
            total: 0,
            message: '就绪',
            file_path: props.settings.video_dir || '.data'
        });

        // 定时更新进度
        let progressInterval = null;
        const validItems = computed(() =>
            downloadItems.value
                .map(item => ({
                    link: (item.link || '').trim(),
                    file_name: (item.file_name || '').trim()
                }))
                .filter(item => item.link)
        );
        const realtimePercentage = computed(() => {
            const downloaded = Number(progress.value.downloaded || 0);
            const total = Number(progress.value.total || 0);
            if (total > 0) {
                return Math.min(100, (downloaded / total) * 100);
            }
            return Number(progress.value.percentage || 0);
        });

        const stopProgressPolling = () => {
            if (progressInterval) {
                clearInterval(progressInterval);
                progressInterval = null;
            }
        };

        const fetchProgress = async () => {
            try {
                const result = await props.api.getDownloadProgress();
                const downloaded = Number(result.downloaded || 0);
                const total = Number(result.total || 0);
                const computedPercentage = total > 0
                    ? Math.min(100, (downloaded / total) * 100)
                    : Number(result.percentage || 0);
                progress.value = {
                    status: result.status || 'idle',
                    percentage: computedPercentage,
                    downloaded: downloaded,
                    total: total,
                    message: result.message || '就绪',
                    file_path: result.file_path || savePath.value || props.settings.video_dir
                };

                if (result.status === 'completed') {
                    stopProgressPolling();
                    isLoading.value = false;
                    if (currentTaskStarted.value) {
                        currentTaskStarted.value = false;
                        emit('completed');
                    }
                } else if (result.status === 'error') {
                    stopProgressPolling();
                    isLoading.value = false;
                    currentTaskStarted.value = false;
                } else if (result.status === 'downloading') {
                    isLoading.value = true;
                }
            } catch (error) {
                console.error('获取进度失败', error);
            }
        };

        const startProgressPolling = async () => {
            stopProgressPolling();
            await fetchProgress();
            progressInterval = setInterval(fetchProgress, 1000);
        };

        const browseSavePath = async () => {
            if (isLoading.value || isBrowsing.value) return;

            isBrowsing.value = true;
            try {
                const result = await props.api.browseDirectory();
                if (result.status === 'success' && result.path) {
                    savePath.value = result.path;
                    localStorage.setItem(DOWNLOAD_SAVE_PATH_KEY, result.path);
                }
            } catch (error) {
                console.error('选择目录失败', error);
            } finally {
                isBrowsing.value = false;
            }
        };

        const normalizeVideoName = (value) => {
            const normalized = (value || '')
                .replace(/[^A-Za-z0-9\u4e00-\u9fff]+/g, '_')
                .replace(/_+/g, '_')
                .replace(/^_+|_+$/g, '');
            const parts = normalized.split('_').filter(Boolean);
            return parts.slice(0, 2).join('');
        };

        const normalizeItemName = (item) => {
            item.file_name = normalizeVideoName(item.file_name);
        };

        const hydrateItemName = async (idx) => {
            const item = downloadItems.value[idx];
            const targetLink = (item?.link || '').trim();
            if (!item || item.isParsing || !targetLink) return;

            item.isParsing = true;
            try {
                const result = await props.api.parseVideoInfo(targetLink);
                const suggestedName = result.title || result.description || result.video_id || '';
                if (suggestedName && !item.file_name) {
                    item.file_name = normalizeVideoName(suggestedName);
                }
            } catch (error) {
                console.error('解析视频信息失败', error);
            } finally {
                item.isParsing = false;
            }
        };

        const hydrateAllItemNames = async () => {
            if (isBatchParsing.value) return;
            isBatchParsing.value = true;
            try {
                for (let i = 0; i < downloadItems.value.length; i += 1) {
                    await hydrateItemName(i);
                }
            } finally {
                isBatchParsing.value = false;
            }
        };

        const addItem = () => {
            if (downloadItems.value.length >= MAX_BATCH_ITEMS) return;
            downloadItems.value.push(createEmptyItem());
        };

        const removeItem = (idx) => {
            if (downloadItems.value.length <= 1) return;
            downloadItems.value.splice(idx, 1);
        };

        const submit = async () => {
            if (validItems.value.length === 0) return;
            if (validItems.value.length > MAX_BATCH_ITEMS) {
                alert(`单次最多支持 ${MAX_BATCH_ITEMS} 条下载任务`);
                return;
            }

            isLoading.value = true;
            currentTaskStarted.value = true;
            progress.value = {
                status: 'downloading',
                percentage: 0,
                downloaded: 0,
                total: 0,
                message: '正在启动下载任务...',
                file_path: savePath.value || props.settings.video_dir
            };

            try {
                await startProgressPolling();
                const payloadTasks = validItems.value.map(item => ({
                    link: item.link,
                    file_name: item.file_name || undefined
                }));
                const result = await props.api.downloadVideo(
                    payloadTasks,
                    savePath.value
                );
                progress.value = {
                    ...progress.value,
                    file_path: result.save_path || progress.value.file_path,
                    message: `已启动 ${result.total_count || payloadTasks.length} 个任务`
                };
                downloadItems.value = [createEmptyItem()];
            } catch (error) {
                stopProgressPolling();
                isLoading.value = false;
                currentTaskStarted.value = false;
                progress.value = {
                    ...progress.value,
                    status: 'error',
                    message: `下载失败: ${error.message || error}`
                };
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

        watch(
            () => props.settings.video_dir,
            (newValue) => {
                if (!savePath.value || progress.value.status === 'idle') {
                    savePath.value = localStorage.getItem(DOWNLOAD_SAVE_PATH_KEY) || newValue || '.data';
                }
            },
            { immediate: true }
        );

        onMounted(async () => {
            await fetchProgress();
            if (progress.value.status === 'downloading') {
                progressInterval = setInterval(fetchProgress, 1000);
            }
        });

        onBeforeUnmount(() => {
            stopProgressPolling();
        });

        return {
            downloadItems,
            validItems,
            savePath,
            isLoading,
            isBrowsing,
            isBatchParsing,
            progress,
            realtimePercentage,
            submit,
            browseSavePath,
            hydrateItemName,
            hydrateAllItemNames,
            normalizeItemName,
            addItem,
            removeItem,
            MAX_BATCH_ITEMS,
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
                <div class="row">
                    <button class="btn btn-secondary" @click="toggleSelectAll">
                        {{ allSelected ? '取消全选' : '全选' }}
                    </button>
                    <button
                        class="btn btn-danger"
                        @click="deleteSelected"
                        :disabled="selectedIds.length === 0"
                    >
                        🗑️ 批量删除
                    </button>
                    <button class="btn btn-primary" @click="reload">
                        🔄 刷新
                    </button>
                </div>
            </div>

            <div v-if="videos.length === 0" class="card text-center">
                <p style="padding: 40px 0; color: #999;">
                    还没有下载过视频 <br/>
                    去<a href="#" @click.prevent="$parent.currentPage = 'download'">视频下载</a>开始吧
                </p>
            </div>

            <div v-else>
                <div class="card" style="padding: 14px 20px;">
                    已选择 {{ selectedIds.length }} / {{ videos.length }} 个视频
                    <span v-if="batchActionMessage" class="inline-feedback">{{ batchActionMessage }}</span>
                </div>
                <table class="table">
                    <thead>
                        <tr>
                            <th>
                                <input
                                    type="checkbox"
                                    :checked="allSelected"
                                    @change="toggleSelectAll"
                                />
                            </th>
                            <th>标题</th>
                            <th>具体路径</th>
                            <th>文件大小</th>
                            <th>创建时间</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="video in videos" :key="video.video_id">
                            <td>
                                <input
                                    type="checkbox"
                                    :checked="selectedIds.includes(video.video_id)"
                                    @change="toggleSelection(video.video_id)"
                                />
                            </td>
                            <td class="truncate" :title="video.title">{{ video.title }}</td>
                            <td>
                                <div class="path-cell" :title="video.file_path">{{ video.file_path }}</div>
                                <div class="path-actions mt-1">
                                    <button
                                        class="btn btn-secondary btn-small"
                                        @click="copyPath(video.file_path)"
                                    >
                                        复制路径
                                    </button>
                                    <span
                                        v-if="copiedPath === video.file_path"
                                        class="copy-hint"
                                    >
                                        已复制
                                    </span>
                                </div>
                            </td>
                            <td>{{ formatBytes(video.file_size) }}</td>
                            <td>{{ formatDate(video.created_at) }}</td>
                            <td>
                                <div class="action-group">
                                    <button
                                        class="btn btn-secondary btn-small"
                                        @click="openVideo(video.video_id)"
                                    >
                                        打开
                                    </button>
                                    <button
                                        class="btn btn-secondary btn-small"
                                        @click="openVideoFolder(video.video_id)"
                                    >
                                        打开文件夹
                                    </button>
                                    <button 
                                        class="btn btn-danger btn-small"
                                        @click="deleteVideo(video.video_id)"
                                    >
                                        🗑️ 删除
                                    </button>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    `,

    setup(props, { emit }) {
        const selectedIds = ref([]);
        const copiedPath = ref('');
        const batchActionMessage = ref('');
        let copyHintTimer = null;
        let batchActionTimer = null;
        const allSelected = computed(
            () => props.videos.length > 0 && selectedIds.value.length === props.videos.length
        );

        const reload = () => {
            selectedIds.value = [];
            emit('reload');
        };

        const toggleSelection = (videoId) => {
            if (selectedIds.value.includes(videoId)) {
                selectedIds.value = selectedIds.value.filter(id => id !== videoId);
                return;
            }
            selectedIds.value = [...selectedIds.value, videoId];
        };

        const toggleSelectAll = () => {
            if (allSelected.value) {
                selectedIds.value = [];
                return;
            }
            selectedIds.value = props.videos.map(video => video.video_id);
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

        const deleteSelected = async () => {
            if (selectedIds.value.length === 0) return;
            if (!confirm(`确定要删除选中的 ${selectedIds.value.length} 个视频吗？`)) return;

            try {
                await props.api.batchDeleteVideos(selectedIds.value);
                reload();
                batchActionMessage.value = '已批量删除选中视频';
                if (batchActionTimer) {
                    clearTimeout(batchActionTimer);
                }
                batchActionTimer = setTimeout(() => {
                    batchActionMessage.value = '';
                    batchActionTimer = null;
                }, 2000);
            } catch (error) {
                alert('❌ 批量删除失败: ' + (error.message || error));
            }
        };

        const openVideo = async (videoId) => {
            try {
                await props.api.openVideo(videoId);
            } catch (error) {
                alert('❌ 打开视频失败: ' + (error.message || error));
            }
        };

        const openVideoFolder = async (videoId) => {
            try {
                await props.api.openVideoFolder(videoId);
            } catch (error) {
                alert('❌ 打开文件夹失败: ' + (error.message || error));
            }
        };

        const copyPath = async (filePath) => {
            try {
                await navigator.clipboard.writeText(filePath);
                copiedPath.value = filePath;
                if (copyHintTimer) {
                    clearTimeout(copyHintTimer);
                }
                copyHintTimer = setTimeout(() => {
                    copiedPath.value = '';
                    copyHintTimer = null;
                }, 2000);
            } catch (error) {
                alert('❌ 复制路径失败: ' + (error.message || error));
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
            selectedIds,
            copiedPath,
            batchActionMessage,
            allSelected,
            toggleSelection,
            toggleSelectAll,
            deleteVideo,
            deleteSelected,
            openVideo,
            openVideoFolder,
            copyPath,
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
                    <div class="row">
                        <div class="col">
                            <input 
                                :value="formData.video_dir"
                                type="text"
                                placeholder="请选择视频保存目录"
                                readonly
                            />
                        </div>
                        <div style="display: flex; align-items: end;">
                            <button
                                class="btn btn-secondary"
                                @click="browseVideoDir"
                                :disabled="isBrowsing"
                            >
                                <span v-if="!isBrowsing">📁 浏览</span>
                                <span v-else>选择中...</span>
                            </button>
                        </div>
                    </div>
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        默认值: .data
                    </p>
                </div>

                <div class="form-group">
                    <label>下载超时时间 (秒)</label>
                    <input 
                        v-model.number="formData.download_timeout"
                        type="number"
                        min="60"
                        max="1800"
                    />
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        建议保留 1200 秒左右，可支持约 20 分钟视频的完整下载过程
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
        const isBrowsing = ref(false);

        const browseVideoDir = async () => {
            if (isBrowsing.value) return;

            isBrowsing.value = true;
            try {
                const result = await props.api.browseDirectory();
                if (result.status === 'success' && result.path) {
                    formData.video_dir = result.path;
                    localStorage.setItem(DOWNLOAD_SAVE_PATH_KEY, result.path);
                }
            } catch (error) {
                alert('❌ 选择目录失败: ' + (error.message || error));
            } finally {
                isBrowsing.value = false;
            }
        };

        const save = async () => {
            try {
                emit('save', formData);
            } catch (error) {
                alert('❌ 保存失败: ' + (error.message || error));
            }
        };

        return {
            formData,
            isBrowsing,
            browseVideoDir,
            save
        };
    }
});

// ============================================================================
// 微信视频号上传页面组件
// ============================================================================

app.component('weixin-page', {
    props: ['api'],
    template: `
        <div>
            <div class="header">
                <h1>📤 视频号上传管理</h1>
                <p>管理视频号账号、上传视频、设置定时发布</p>
            </div>

            <!-- 消息提示 -->
            <div v-if="message.show" :class="['alert', 'alert-' + message.type]">
                {{ message.text }}
            </div>

            <!-- 标签页 -->
            <div class="tabs">
                <div :class="['tab', { active: tab === 'accounts' }]" @click="tab = 'accounts'">账号管理</div>
                <div :class="['tab', { active: tab === 'upload' }]" @click="tab = 'upload'">上传视频</div>
                <div :class="['tab', { active: tab === 'tasks' }]" @click="tab = 'tasks'; loadTasks()">任务列表</div>
                <div :class="['tab', { active: tab === 'schedule' }]" @click="tab = 'schedule'">定时发布</div>
            </div>

            <!-- 账号管理 -->
            <div v-if="tab === 'accounts'">
                <div class="card">
                    <div class="flex-between" style="margin-bottom: 16px;">
                        <div class="card-title" style="margin-bottom: 0;">视频号账号</div>
                        <button class="btn btn-primary btn-small" @click="showAddAccount = true">+ 添加账号</button>
                    </div>
                    <table class="table" v-if="accounts.length">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>名称</th>
                                <th>微信ID</th>
                                <th>状态</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="acc in accounts" :key="acc.id">
                                <td>{{ acc.id }}</td>
                                <td>{{ acc.name }}</td>
                                <td>{{ acc.wechat_id || '-' }}</td>
                                <td><span :class="'badge badge-' + getStatusClass(acc.status)">{{ getStatusText(acc.status) }}</span></td>
                                <td>{{ formatDate(acc.created_at) }}</td>
                                <td>
                                    <div class="action-group">
                                        <button class="btn btn-primary btn-small" @click="loginAccount(acc.id)" :disabled="acc.status === 'logging_in'">
                                            {{ acc.status === 'logging_in' ? '扫码中...' : '扫码登录' }}
                                        </button>
                                        <button class="btn btn-secondary btn-small" @click="refreshAccount(acc.id)">刷新</button>
                                        <button class="btn btn-danger btn-small" @click="deleteAccount(acc.id)">删除</button>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    <div v-else class="empty-state">暂无账号，点击"添加账号"开始</div>
                </div>
            </div>

            <!-- 上传视频 -->
            <div v-if="tab === 'upload'">
                <div class="card">
                    <div class="card-title">上传视频</div>
                    <div class="form-group">
                        <label>选择账号</label>
                        <select v-model="uploadForm.account_id">
                            <option value="">请选择账号</option>
                            <option v-for="acc in accounts.filter(a => a.status === 'active')" :key="acc.id" :value="acc.id">
                                {{ acc.name }}
                            </option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>视频文件路径</label>
                        <input v-model="uploadForm.video_path" type="text" placeholder="输入视频文件的完整路径，如 C:\\Videos\\test.mp4">
                    </div>
                    <div class="form-group">
                        <label>元数据来源</label>
                        <select v-model="uploadForm.metadata_source">
                            <option value="manual">手动填写</option>
                            <option value="filename">从文件名读取</option>
                            <option value="directory">从目录名读取</option>
                            <option value="ai">AI 自动生成</option>
                        </select>
                    </div>
                    <div v-if="uploadForm.metadata_source === 'manual'">
                        <div class="form-group">
                            <label>标题</label>
                            <input v-model="uploadForm.title" type="text" placeholder="视频标题（最多50字）" maxlength="50">
                        </div>
                        <div class="form-group">
                            <label>描述</label>
                            <textarea v-model="uploadForm.description" placeholder="视频描述"></textarea>
                        </div>
                        <div class="form-group">
                            <label>标签（用逗号分隔）</label>
                            <input v-model="uploadForm.tagsStr" type="text" placeholder="标签1, 标签2, 标签3">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>定时发布（可选）</label>
                        <input type="datetime-local" v-model="uploadForm.scheduled_at">
                    </div>
                    <button class="btn btn-success btn-block" @click="createUploadTask" :disabled="!uploadForm.account_id || !uploadForm.video_path">
                        {{ uploadForm.scheduled_at ? '定时上传' : '立即上传' }}
                    </button>
                </div>

                <div class="card">
                    <div class="card-title">批量上传</div>
                    <div class="form-group">
                        <label>选择账号</label>
                        <select v-model="batchForm.account_id">
                            <option value="">请选择账号</option>
                            <option v-for="acc in accounts.filter(a => a.status === 'active')" :key="acc.id" :value="acc.id">
                                {{ acc.name }}
                            </option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>视频文件路径（每行一个）</label>
                        <textarea v-model="batchForm.video_paths" rows="5" placeholder="C:\\Videos\\video1.mp4&#10;C:\\Videos\\video2.mp4&#10;C:\\Videos\\video3.mp4"></textarea>
                    </div>
                    <div class="form-group">
                        <label>标签（所有视频共用，用逗号分隔）</label>
                        <input v-model="batchForm.tagsStr" type="text" placeholder="标签1, 标签2">
                    </div>
                    <div class="form-group">
                        <label>元数据来源</label>
                        <select v-model="batchForm.metadata_source">
                            <option value="manual">手动填写</option>
                            <option value="filename">从文件名读取</option>
                            <option value="directory">从目录名读取</option>
                        </select>
                    </div>
                    <button class="btn btn-success btn-block" @click="createBatchUpload" :disabled="!batchForm.account_id || !batchForm.video_paths">
                        批量上传
                    </button>
                </div>
            </div>

            <!-- 任务列表 -->
            <div v-if="tab === 'tasks'">
                <div class="card">
                    <div class="flex-between" style="margin-bottom: 16px;">
                        <div class="card-title" style="margin-bottom: 0;">上传任务</div>
                        <button class="btn btn-secondary btn-small" @click="loadTasks()">刷新</button>
                    </div>
                    <table class="table" v-if="tasks.length">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>账号</th>
                                <th>视频</th>
                                <th>标题</th>
                                <th>状态</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="task in tasks" :key="task.id">
                                <td>{{ task.id }}</td>
                                <td>{{ getAccountName(task.account_id) }}</td>
                                <td>{{ getFileName(task.video_path) }}</td>
                                <td>{{ task.title || '-' }}</td>
                                <td><span :class="'badge badge-' + getTaskStatusClass(task.status)">{{ getTaskStatusText(task.status) }}</span></td>
                                <td>{{ formatDate(task.created_at) }}</td>
                                <td>
                                    <div class="action-group">
                                        <button v-if="task.status === 'failed'" class="btn btn-primary btn-small" @click="retryTask(task.id)">重试</button>
                                        <button class="btn btn-danger btn-small" @click="deleteTask(task.id)">删除</button>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    <div v-else class="empty-state">暂无上传任务</div>
                </div>
            </div>

            <!-- 定时发布 -->
            <div v-if="tab === 'schedule'">
                <div class="card">
                    <div class="card-title">创建定时计划</div>
                    <div class="form-group">
                        <label>选择账号</label>
                        <select v-model="scheduleForm.account_id">
                            <option value="">请选择账号</option>
                            <option v-for="acc in accounts.filter(a => a.status === 'active')" :key="acc.id" :value="acc.id">
                                {{ acc.name }}
                            </option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>视频文件路径（每行一个）</label>
                        <textarea v-model="scheduleForm.video_paths" rows="5" placeholder="C:\\Videos\\video1.mp4&#10;C:\\Videos\\video2.mp4"></textarea>
                    </div>
                    <div class="form-group">
                        <label>调度方式</label>
                        <select v-model="scheduleForm.schedule_type">
                            <option value="interval">按间隔</option>
                            <option value="cron">Cron 表达式</option>
                        </select>
                    </div>
                    <div v-if="scheduleForm.schedule_type === 'interval'" class="form-group">
                        <label>间隔（分钟）</label>
                        <input type="number" v-model.number="scheduleForm.interval_minutes" min="1" placeholder="60">
                    </div>
                    <div v-if="scheduleForm.schedule_type === 'cron'" class="form-group">
                        <label>Cron 表达式</label>
                        <input v-model="scheduleForm.cron_expr" type="text" placeholder="0 9 * * * (每天9点)">
                    </div>
                    <div class="form-group">
                        <label>标签（用逗号分隔）</label>
                        <input v-model="scheduleForm.tagsStr" type="text" placeholder="标签1, 标签2">
                    </div>
                    <button class="btn btn-success btn-block" @click="createSchedule" :disabled="!scheduleForm.account_id || !scheduleForm.video_paths">
                        创建定时计划
                    </button>
                </div>

                <div class="card">
                    <div class="flex-between" style="margin-bottom: 16px;">
                        <div class="card-title" style="margin-bottom: 0;">定时计划列表</div>
                        <button class="btn btn-secondary btn-small" @click="loadSchedules()">刷新</button>
                    </div>
                    <table class="table" v-if="schedules.length">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>账号</th>
                                <th>视频数</th>
                                <th>调度</th>
                                <th>下次执行</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="s in schedules" :key="s.id">
                                <td>{{ s.id }}</td>
                                <td>{{ getAccountName(s.account_id) }}</td>
                                <td>{{ s.video_paths ? s.video_paths.length : 0 }}</td>
                                <td>{{ s.cron_expr || '每 ' + s.interval_minutes + ' 分钟' }}</td>
                                <td>{{ s.next_run_at || '-' }}</td>
                                <td>
                                    <button class="btn btn-danger btn-small" @click="deleteSchedule(s.id)">删除</button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    <div v-else class="empty-state">暂无定时计划</div>
                </div>
            </div>

            <!-- 添加账号弹窗 -->
            <div v-if="showAddAccount" class="modal-overlay" @click.self="showAddAccount = false">
                <div class="modal-box">
                    <h3>添加视频号账号</h3>
                    <div class="form-group">
                        <label>账号名称</label>
                        <input v-model="newAccountName" type="text" placeholder="给账号起个名字，如：我的视频号1">
                    </div>
                    <p class="text-muted" style="font-size: 13px; margin-top: 8px;">
                        创建后需要扫码登录才能使用。每个账号需要在微信中扫码确认。
                    </p>
                    <div class="modal-actions">
                        <button class="btn btn-secondary" @click="showAddAccount = false">取消</button>
                        <button class="btn btn-primary" @click="addAccount" :disabled="!newAccountName">创建并登录</button>
                    </div>
                </div>
            </div>
        </div>
    `,

    setup(props) {
        const tab = ref('accounts');
        const accounts = ref([]);
        const tasks = ref([]);
        const schedules = ref([]);
        const showAddAccount = ref(false);
        const newAccountName = ref('');
        const message = reactive({ show: false, type: 'info', text: '' });

        const uploadForm = reactive({
            account_id: '', video_path: '', title: '', description: '',
            tagsStr: '', metadata_source: 'manual', scheduled_at: ''
        });
        const batchForm = reactive({
            account_id: '', video_paths: '', tagsStr: '', metadata_source: 'manual'
        });
        const scheduleForm = reactive({
            account_id: '', video_paths: '', schedule_type: 'interval',
            interval_minutes: 60, cron_expr: '', tagsStr: '', metadata_source: 'manual'
        });

        function showMessage(text, type = 'info') {
            message.show = true;
            message.type = type;
            message.text = text;
            setTimeout(() => message.show = false, 3000);
        }

        function formatDate(s) {
            if (!s) return '-';
            return new Date(s).toLocaleString('zh-CN');
        }

        function getFileName(p) {
            return p ? p.split(/[/\\\\]/).pop() : '-';
        }

        function getAccountName(id) {
            const a = accounts.value.find(a => a.id === id);
            return a ? a.name : '#' + id;
        }

        function getStatusClass(s) {
            return { active: 'active', expired: 'expired', error: 'error', logging_in: 'pending' }[s] || '';
        }

        function getStatusText(s) {
            return { active: '正常', expired: '已过期', error: '异常', logging_in: '扫码中' }[s] || s;
        }

        function getTaskStatusClass(s) {
            return { pending: 'pending', uploading: 'uploading', completed: 'completed', failed: 'failed' }[s] || '';
        }

        function getTaskStatusText(s) {
            return {
                pending: '等待中', uploading: '上传中', processing: '处理中',
                filling: '填写中', publishing: '发布中', completed: '已完成',
                failed: '失败', cancelled: '已取消'
            }[s] || s;
        }

        async function loadAccounts() {
            try {
                const res = await props.api.getWeixinAccounts();
                accounts.value = res.accounts || [];
            } catch (e) {
                console.error(e);
            }
        }

        async function loadTasks() {
            try {
                const res = await props.api.getWeixinTasks();
                tasks.value = res.tasks || [];
            } catch (e) {
                console.error(e);
            }
        }

        async function loadSchedules() {
            try {
                const res = await props.api.getWeixinSchedules();
                schedules.value = res.schedules || [];
            } catch (e) {
                console.error(e);
            }
        }

        async function addAccount() {
            try {
                await props.api.createWeixinAccount(newAccountName.value);
                showAddAccount.value = false;
                newAccountName.value = '';
                await loadAccounts();
                showMessage('账号已创建，请点击"扫码登录"', 'success');
            } catch (e) {
                showMessage('创建失败: ' + (e.message || e), 'error');
            }
        }

        async function loginAccount(id) {
            try {
                await props.api.loginWeixinAccount(id);
                showMessage('扫码登录已启动，请在弹出的浏览器窗口中扫码', 'info');
                const timer = setInterval(async () => {
                    await loadAccounts();
                    const acc = accounts.value.find(a => a.id === id);
                    if (acc && acc.status !== 'logging_in') {
                        clearInterval(timer);
                        if (acc.status === 'active') showMessage('登录成功！', 'success');
                    }
                }, 2000);
            } catch (e) {
                showMessage('登录失败: ' + (e.message || e), 'error');
            }
        }

        async function refreshAccount(id) {
            try {
                const res = await props.api.refreshWeixinAccount(id);
                await loadAccounts();
                showMessage(res.message, res.status === 'success' ? 'success' : 'info');
            } catch (e) {
                showMessage('刷新失败: ' + (e.message || e), 'error');
            }
        }

        async function deleteAccount(id) {
            if (!confirm('确定删除该账号？')) return;
            try {
                await props.api.deleteWeixinAccount(id);
                await loadAccounts();
                showMessage('账号已删除', 'success');
            } catch (e) {
                showMessage('删除失败', 'error');
            }
        }

        async function createUploadTask() {
            try {
                const tags = uploadForm.tagsStr ? uploadForm.tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];
                const payload = {
                    account_id: parseInt(uploadForm.account_id),
                    video_path: uploadForm.video_path,
                    title: uploadForm.title || null,
                    description: uploadForm.description || null,
                    tags: tags.length ? tags : null,
                    metadata_source: uploadForm.metadata_source,
                    scheduled_at: uploadForm.scheduled_at ? new Date(uploadForm.scheduled_at).toISOString() : null,
                };
                const res = await props.api.createWeixinUpload(payload);
                showMessage(res.message || '任务已创建', 'success');
                uploadForm.video_path = '';
                uploadForm.title = '';
                uploadForm.description = '';
                uploadForm.tagsStr = '';
                uploadForm.scheduled_at = '';
            } catch (e) {
                showMessage('创建失败: ' + (e.message || e), 'error');
            }
        }

        async function createBatchUpload() {
            try {
                const paths = batchForm.video_paths.split('\n').map(p => p.trim()).filter(Boolean);
                if (!paths.length) {
                    showMessage('请输入视频路径', 'error');
                    return;
                }
                const tags = batchForm.tagsStr ? batchForm.tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];
                const res = await props.api.createWeixinBatchUpload({
                    account_id: parseInt(batchForm.account_id),
                    video_paths: paths,
                    tags: tags.length ? tags : null,
                    metadata_source: batchForm.metadata_source,
                });
                showMessage('批量任务已创建，共 ' + res.total + ' 个', 'success');
                batchForm.video_paths = '';
                batchForm.tagsStr = '';
            } catch (e) {
                showMessage('创建失败: ' + (e.message || e), 'error');
            }
        }

        async function retryTask(id) {
            try {
                await props.api.retryWeixinTask(id);
                showMessage('重试任务已启动', 'success');
                await loadTasks();
            } catch (e) {
                showMessage('重试失败: ' + (e.message || e), 'error');
            }
        }

        async function deleteTask(id) {
            if (!confirm('确定删除该任务？')) return;
            try {
                await props.api.deleteWeixinTask(id);
                await loadTasks();
                showMessage('任务已删除', 'success');
            } catch (e) {
                showMessage('删除失败', 'error');
            }
        }

        async function createSchedule() {
            try {
                const paths = scheduleForm.video_paths.split('\n').map(p => p.trim()).filter(Boolean);
                if (!paths.length) {
                    showMessage('请输入视频路径', 'error');
                    return;
                }
                const tags = scheduleForm.tagsStr ? scheduleForm.tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];
                const payload = {
                    account_id: parseInt(scheduleForm.account_id),
                    video_paths: paths,
                    tags: tags.length ? tags : null,
                    metadata_source: scheduleForm.metadata_source,
                };
                if (scheduleForm.schedule_type === 'interval') {
                    payload.interval_minutes = scheduleForm.interval_minutes;
                } else {
                    payload.cron_expr = scheduleForm.cron_expr;
                }
                await props.api.createWeixinSchedule(payload);
                showMessage('定时计划已创建', 'success');
                await loadSchedules();
            } catch (e) {
                showMessage('创建失败: ' + (e.message || e), 'error');
            }
        }

        async function deleteSchedule(id) {
            if (!confirm('确定删除该定时计划？')) return;
            try {
                await props.api.deleteWeixinSchedule(id);
                await loadSchedules();
                showMessage('定时计划已删除', 'success');
            } catch (e) {
                showMessage('删除失败', 'error');
            }
        }

        onMounted(() => {
            loadAccounts();
            loadSchedules();
        });

        return {
            tab, accounts, tasks, schedules, showAddAccount, newAccountName, message,
            uploadForm, batchForm, scheduleForm,
            formatDate, getFileName, getAccountName,
            getStatusClass, getStatusText, getTaskStatusClass, getTaskStatusText,
            loadAccounts, loadTasks, loadSchedules,
            addAccount, loginAccount, refreshAccount, deleteAccount,
            createUploadTask, createBatchUpload,
            retryTask, deleteTask,
            createSchedule, deleteSchedule, showMessage
        };
    }
});

// ============================================================================
// 挂载应用
// ============================================================================

app.mount('#app');
