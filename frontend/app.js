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
// 挂载应用
// ============================================================================

app.mount('#app');
