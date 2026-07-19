/**
 * ViralDramaBot - Vue 3 Frontend Application
 * 
 * 主要功能：
 * - 下载视频表单
 * - 视频管理列表
 * - 应用设置
 * - 完整的短剧处理流程
 */

const { createApp, ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } = Vue;

// ============================================================================
// API 客户端
// ============================================================================

const API_BASE_URL = `${window.location.origin}/api`;
const DOWNLOAD_SAVE_PATH_KEY = "viraldramabot.download.savePath";
const MAX_BATCH_ITEMS = 50;

const getDesktopApi = () => window.pywebview?.api;
const getErrorMessage = (error) => {
    if (!error) return '未知错误';
    if (typeof error === 'string') return error;
    if (error.detail) return getErrorMessage(error.detail);
    if (error.message) return getErrorMessage(error.message);
    if (error.error) return getErrorMessage(error.error);
    try {
        return JSON.stringify(error);
    } catch (_) {
        return String(error);
    }
};

const api = {
    getDashboard: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/dashboard`);
            return response.data;
        } catch (error) {
            throw getErrorMessage(error.response?.data || error);
        }
    },

    getDashboardTraffic: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/dashboard/traffic`);
            return response.data;
        } catch (error) {
            throw getErrorMessage(error.response?.data || error);
        }
    },

    refreshDashboardTraffic: async (hours = 24) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/dashboard/traffic/refresh`, null, {
                params: { hours }
            });
            return response.data;
        } catch (error) {
            throw getErrorMessage(error.response?.data || error);
        }
    },

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
            const desktopApi = getDesktopApi();
            if (desktopApi?.browseDirectory) {
                return await desktopApi.browseDirectory();
            }
            const response = await axios.get(`${API_BASE_URL}/browse-directory`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    /**
     * 选择多个视频文件
     */
    browseFiles: async () => {
        try {
            const desktopApi = getDesktopApi();
            if (desktopApi?.browseFiles) {
                try {
                    const result = await desktopApi.browseFiles();
                    if (!result || result.status !== 'error') {
                        return result;
                    }
                    console.warn('Desktop file dialog failed, falling back to backend API:', result);
                } catch (desktopError) {
                    console.warn('Desktop file dialog failed, falling back to backend API:', desktopError);
                }
            }
            const response = await axios.get(`${API_BASE_URL}/browse-files`);
            return response.data;
        } catch (error) {
            throw getErrorMessage(error.response?.data || error);
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

    testWeixinProxy: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/weixin/proxy/test`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    getWeixinProxyProfiles: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/weixin/proxy-profiles`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    createWeixinProxyProfile: async (payload) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/proxy-profiles`, payload);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    updateWeixinProxyProfile: async (id, payload) => {
        try {
            const response = await axios.put(`${API_BASE_URL}/weixin/proxy-profiles/${id}`, payload);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    deleteWeixinProxyProfile: async (id) => {
        try {
            const response = await axios.delete(`${API_BASE_URL}/weixin/proxy-profiles/${id}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    checkWeixinProxyProfile: async (id) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/proxy-profiles/${id}/check`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    checkAllWeixinProxyProfiles: async () => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/proxy-profiles/check-all`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    listWeixinFavoriteLocations: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/weixin/favorite-locations`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    createWeixinFavoriteLocation: async (name) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/favorite-locations`, { name });
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    deleteWeixinFavoriteLocation: async (id) => {
        try {
            const response = await axios.delete(`${API_BASE_URL}/weixin/favorite-locations/${id}`);
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

    cleanupMaintenance: async (payload) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/maintenance/cleanup`, payload);
            return response.data;
        } catch (error) {
            throw getErrorMessage(error.response?.data || error);
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
            const payload = name ? { name } : {};
            const response = await axios.post(`${API_BASE_URL}/weixin/accounts`, payload);
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

    loginWeixinAccountEmbedded: async (id) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/accounts/${id}/login-embedded`);
            return response.data;
        } catch (error) {
            throw getErrorMessage(error.response?.data || error);
        }
    },

    getWeixinLoginSession: async (sessionId) => {
        try {
            const response = await axios.get(`${API_BASE_URL}/weixin/login-sessions/${sessionId}`);
            return response.data;
        } catch (error) {
            throw getErrorMessage(error.response?.data || error);
        }
    },

    cancelWeixinLoginSession: async (sessionId) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/login-sessions/${sessionId}/cancel`);
            return response.data;
        } catch (error) {
            throw getErrorMessage(error.response?.data || error);
        }
    },

    sendWeixinBrowserInput: async (sessionId, payload) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/login-sessions/${sessionId}/input`, payload);
            return response.data;
        } catch (error) {
            throw getErrorMessage(error.response?.data || error);
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

    openWeixinPostList: async (id) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/accounts/${id}/open-post-list`);
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

    deleteWeixinAccounts: async (accountIds) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/accounts/batch-delete`, {
                account_ids: accountIds
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    scanWeixinTraffic: async (accountId, payload) => {
        try {
            const response = await axios.post(
                `${API_BASE_URL}/weixin/accounts/${accountId}/traffic/scan`,
                payload
            );
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    getWeixinTrafficScanStatus: async (accountId) => {
        try {
            const response = await axios.get(
                `${API_BASE_URL}/weixin/accounts/${accountId}/traffic/scan-status`
            );
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    deleteWeixinTrafficPosts: async (accountId, postIds) => {
        try {
            const response = await axios.post(
                `${API_BASE_URL}/weixin/accounts/${accountId}/traffic/delete`,
                { post_ids: postIds }
            );
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    getWeixinAccountsRefreshStatus: async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/weixin/accounts/refresh-status`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    refreshAllWeixinAccounts: async () => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/accounts/refresh-all`);
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

    batchDeleteWeixinTasks: async (taskIds) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/weixin/tasks/batch-delete`, {
                task_ids: taskIds,
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    getLogs: async (since = 0, limit = 200) => {
        try {
            const response = await axios.get(`${API_BASE_URL}/logs`, { params: { since, limit } });
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
// 应用内确认框 / 全局提示（避免浏览器原生 confirm/alert 显示 127.0.0.1）
// ============================================================================

const appConfirmState = reactive({
    show: false,
    title: '确认',
    message: '',
    confirmText: '确定',
    cancelText: '取消',
    danger: true,
    _resolve: null,
});

/**
 * 应用内确认对话框，返回 Promise<boolean>
 * @param {string|{title?:string,message:string,confirmText?:string,cancelText?:string,danger?:boolean}} options
 */
function appConfirm(options) {
    const opts = typeof options === 'string' ? { message: options } : (options || {});
    return new Promise((resolve) => {
        if (appConfirmState._resolve) {
            appConfirmState._resolve(false);
        }
        // 桌面端原生 WebView2 会盖住 HTML 弹窗，确认前先隐藏
        const desktop = typeof getDesktopApi === 'function' ? getDesktopApi() : null;
        if (desktop?.hideWeixinBrowser) {
            try { desktop.hideWeixinBrowser(); } catch (_) {}
        }
        appConfirmState.show = true;
        appConfirmState.title = opts.title || '确认';
        appConfirmState.message = opts.message || '';
        appConfirmState.confirmText = opts.confirmText || '确定';
        appConfirmState.cancelText = opts.cancelText || '取消';
        appConfirmState.danger = opts.danger !== false;
        appConfirmState._resolve = resolve;
    });
}

function resolveAppConfirm(ok) {
    appConfirmState.show = false;
    const resolve = appConfirmState._resolve;
    appConfirmState._resolve = null;
    if (resolve) resolve(!!ok);
}

let _appNotifyImpl = null;

function appNotify(message, type = 'info') {
    const normalized = type === 'error' ? 'danger' : (type || 'info');
    if (_appNotifyImpl) {
        _appNotifyImpl(message, normalized);
        return;
    }
    console.log(`[${normalized}]`, message);
}

// ============================================================================
// Vue 应用
// ============================================================================

const app = createApp({
    template: `
        <transition name="fade">
            <div v-if="loading" class="app-loading-overlay">
                <img src="./logo.png" alt="" class="app-loading-logo">
                <div class="app-loading-spinner"></div>
                <p class="app-loading-text">正在加载中，请稍候…</p>
            </div>
        </transition>
        <div class="container">
            <!-- 侧边栏 -->
            <div class="sidebar">
                <div class="sidebar-logo">
                    <img src="./logo.png" alt="ViralDramaBot" class="logo-img">
                    <span class="logo-text">视频运营助手</span>
                </div>
                <ul class="sidebar-menu">
                    <li>
                        <a
                            :class="{ active: currentPage === 'dashboard' }"
                            @click="currentPage = 'dashboard'"
                        >
                            📊 概览
                        </a>
                    </li>
                    <li>
                        <a 
                            :class="{ active: currentPage === 'download' }"
                            @click="currentPage = 'download'"
                        >
                            📥 素材下载
                        </a>
                    </li>
                    <li>
                        <a 
                            :class="{ active: currentPage === 'videos' }"
                            @click="currentPage = 'videos'"
                        >
                            🎬 素材库
                        </a>
                    </li>
                    <li>
                        <a
                            :class="{ active: currentPage === 'accounts' }"
                            @click="currentPage = 'accounts'"
                        >
                            👤 账号管理
                        </a>
                    </li>
                    <li>
                        <a
                            :class="{ active: currentPage === 'proxies' }"
                            @click="currentPage = 'proxies'"
                        >
                            🌐 代理与位置
                        </a>
                    </li>
                    <li>
                        <a
                            :class="{ active: currentPage === 'logs' }"
                            @click="currentPage = 'logs'"
                        >
                            📋 运行日志
                        </a>
                    </li>
                    <li>
                        <a
                            :class="{ active: currentPage === 'settings' }"
                            @click="currentPage = 'settings'"
                        >
                            ⚙️ 设置
                        </a>
                    </li>
                </ul>
            </div>

            <!-- 主内容区域 -->
            <div class="main-content">
                <!-- 运营概览 -->
                <div v-if="currentPage === 'dashboard'">
                    <dashboard-page
                        :api="api"
                        @navigate="currentPage = $event"
                        @notify="(payload) => showMessage(payload.message, payload.type || 'info')"
                    />
                </div>

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

                <!-- 视频号运营页面：账号管理 / 代理与位置 -->
                <div v-if="['accounts', 'proxies'].includes(currentPage)">
                    <weixin-page
                        :api="api"
                        :initial-tab="weixinTabForPage(currentPage)"
                    />
                </div>

                <!-- 运行日志页面 -->
                <div v-if="currentPage === 'logs'">
                    <logs-page :api="api" />
                </div>
            </div>
        </div>

        <div class="app-toast-stack">
            <div
                v-for="msg in messages"
                :key="msg.id"
                :class="['alert', 'alert-' + msg.type, 'app-toast']"
            >{{ msg.message }}</div>
        </div>

        <div
            v-if="appConfirmState.show"
            class="modal-overlay app-confirm-overlay"
            @click.self="resolveAppConfirm(false)"
        >
            <div class="modal-box">
                <h3>{{ appConfirmState.title }}</h3>
                <p class="app-confirm-message">{{ appConfirmState.message }}</p>
                <div class="modal-actions">
                    <button class="btn btn-secondary" @click="resolveAppConfirm(false)">
                        {{ appConfirmState.cancelText }}
                    </button>
                    <button
                        :class="['btn', appConfirmState.danger ? 'btn-danger' : 'btn-primary']"
                        @click="resolveAppConfirm(true)"
                    >{{ appConfirmState.confirmText }}</button>
                </div>
            </div>
        </div>
    `,

    setup() {
        const loading = ref(true);
        const currentPage = ref('dashboard');
        const videos = ref([]);
        const settings = ref({
            video_dir: '.data',
            download_timeout: 1200,
            max_retries: 3,
            weixin_upload_timeout: 600,
            weixin_inter_upload_cooldown: 30,
            weixin_max_retries: 3,
            weixin_proxy_enabled: true,
            weixin_proxy_scheme: 'http',
            weixin_proxy_host: '127.0.0.1',
            weixin_proxy_port: 0,
            weixin_location_mode: 'proxy_ip'
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
            const normalized = type === 'error' ? 'danger' : (type || 'info');
            const id = Date.now();
            messages.value.push({ id, message, type: normalized });
            setTimeout(() => {
                messages.value = messages.value.filter(m => m.id !== id);
            }, 3000);
        };
        _appNotifyImpl = showMessage;

        const handleDownloadCompleted = () => {
            loadVideos();
            showMessage('✅ 视频下载完成，已刷新视频列表', 'success');
        };

        const weixinTabForPage = (page) => ({
            accounts: 'accounts',
            proxies: 'proxies',
        }[page] || 'accounts');

        // 桌面端 WebView2 与 DOM 脱钩：离开账号工作区时必须主动 hide，避免浮层盖住其它页
        watch(currentPage, (page) => {
            if (!['accounts', 'proxies'].includes(page)) {
                const desktop = getDesktopApi();
                if (desktop?.hideWeixinBrowser) desktop.hideWeixinBrowser();
            }
        });

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

        // 页面加载时初始化，两个请求都完成后移除遮罩
        onMounted(async () => {
            try {
                await Promise.all([loadVideos(), loadSettings()]);
            } finally {
                loading.value = false;
            }
        });

        return {
            loading,
            currentPage,
            videos,
            settings,
            messages,
            appConfirmState,
            resolveAppConfirm,
            api,
            loadVideos,
            loadSettings,
            showMessage,
            handleDownloadCompleted,
            weixinTabForPage,
            handleSaveSettings
        };
    }
});

// ============================================================================
// 运营概览组件
// ============================================================================

app.component('dashboard-page', {
    props: ['api'],
    emits: ['navigate', 'notify'],
    template: `
        <div>
            <div class="header">
                <h1>📊 运营工作台</h1>
                <p>集中查看素材、视频号账号、发布队列和代理状态。</p>
            </div>

            <div v-if="error" class="alert alert-danger">{{ error }}</div>

            <div class="card" v-if="loading && !dashboard">
                <span class="spinner"></span> 正在加载概览...
            </div>

            <div v-if="dashboard">
                <div class="row dashboard-metric-row">
                    <div class="col">
                        <div class="card">
                            <div class="card-title">素材库存</div>
                            <div style="font-size: 32px; font-weight: 700;">{{ dashboard.videos?.total || 0 }}</div>
                            <p class="text-muted">已下载视频总数</p>
                            <button class="btn btn-secondary btn-small" @click="$emit('navigate', 'videos')">进入素材库</button>
                        </div>
                    </div>
                    <div class="col">
                        <div class="card">
                            <div class="card-title">视频号账号</div>
                            <div style="font-size: 32px; font-weight: 700;">{{ dashboard.accounts?.total || 0 }}</div>
                            <p class="text-muted">可用 {{ statusCount(dashboard.accounts?.by_status, 'active') }} / 登录中 {{ statusCount(dashboard.accounts?.by_status, 'logging_in') }}</p>
                            <button class="btn btn-secondary btn-small" @click="$emit('navigate', 'accounts')">管理账号</button>
                        </div>
                    </div>
                    <div class="col">
                        <div class="card">
                            <div class="card-title">发布任务</div>
                            <div style="font-size: 32px; font-weight: 700;">{{ dashboard.tasks?.total || 0 }}</div>
                            <p class="text-muted">失败 {{ statusCount(dashboard.tasks?.by_status, 'failed') }} / 完成 {{ statusCount(dashboard.tasks?.by_status, 'completed') }}</p>
                            <button class="btn btn-secondary btn-small" @click="$emit('navigate', 'accounts')">进入账号管理</button>
                        </div>
                    </div>
                    <div class="col">
                        <div class="card">
                            <div class="card-title">代理 Profile</div>
                            <div style="font-size: 32px; font-weight: 700;">{{ dashboard.proxies?.total || 0 }}</div>
                            <p class="text-muted">启用 {{ dashboard.proxies?.enabled || 0 }}</p>
                            <button class="btn btn-secondary btn-small" @click="$emit('navigate', 'proxies')">代理与位置</button>
                        </div>
                    </div>
                    <div class="col">
                        <div class="card">
                            <div class="card-title">上传队列</div>
                            <div style="font-size: 32px; font-weight: 700;">{{ queuePending }}</div>
                            <p class="text-muted">等待中 · {{ queueRunning ? '有任务运行' : '空闲' }}</p>
                            <button class="btn btn-secondary btn-small" @click="$emit('navigate', 'accounts')">进入账号管理</button>
                        </div>
                    </div>
                </div>

                <div class="card" style="margin-top: 8px;">
                    <div class="flex-between" style="align-items: flex-start; gap: 16px; margin-bottom: 16px;">
                        <div>
                            <div class="card-title" style="margin-bottom: 4px;">近 24 小时流量</div>
                            <p class="text-muted" style="font-size: 12px; margin: 0;">
                                平台播放量汇总；剧集排行取作品描述空白符分割后的最后一段（上传时会写成「原描述 + 四空格 + 剧集链接」）。
                                点击按钮后台刷新，可继续浏览其它页面。
                                <span v-if="traffic?.refreshed_at">缓存时间：{{ formatTrafficTime(traffic.refreshed_at) }}</span>
                                <span v-else>暂无缓存，请手动刷新</span>
                            </p>
                        </div>
                        <button
                            class="btn btn-primary btn-small"
                            :disabled="trafficRefreshing || traffic?.is_refreshing"
                            @click="refreshTraffic"
                        >{{ (trafficRefreshing || traffic?.is_refreshing) ? '后台刷新中...' : '刷新流量数据' }}</button>
                    </div>

                    <div v-if="traffic?.top_account" class="alert alert-info" style="margin-bottom: 14px;">
                        流量最大账号：
                        <strong>{{ traffic.top_account.account_name }}</strong>
                        （总播放 {{ traffic.top_account.total_views }}，发表 {{ traffic.top_account.post_count }} 条）
                    </div>
                    <div v-if="traffic?.last_error" class="alert alert-danger" style="margin-bottom: 14px;">
                        上次刷新异常：{{ traffic.last_error }}
                    </div>
                    <div v-if="traffic?.errors?.length" class="text-muted" style="font-size: 12px; margin-bottom: 10px;">
                        部分账号拉取失败：{{ traffic.errors.map(e => e.account_name || ('#' + e.account_id)).join('、') }}
                    </div>

                    <div class="row">
                        <div class="col">
                            <h3 style="font-size: 15px; margin-bottom: 10px;">账号流量排行</h3>
                            <div v-if="trafficAccounts.length" class="account-task-table-wrap">
                                <table class="table" style="margin-bottom: 0;">
                                    <thead>
                                        <tr>
                                            <th>#</th>
                                            <th>账号</th>
                                            <th>发表条数</th>
                                            <th>总播放</th>
                                            <th>最高单条</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="(row, idx) in trafficAccounts" :key="row.account_id">
                                            <td>{{ idx + 1 }}</td>
                                            <td>{{ row.account_name }}</td>
                                            <td>{{ row.post_count }}</td>
                                            <td>{{ row.total_views }}</td>
                                            <td>{{ row.max_views }}</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                            <div v-else class="empty-state" style="padding: 24px 0;">暂无账号流量数据，请刷新</div>
                        </div>
                        <div class="col">
                            <h3 style="font-size: 15px; margin-bottom: 10px;">最火剧集排行</h3>
                            <div v-if="trafficDramas.length" class="account-task-table-wrap">
                                <table class="table" style="margin-bottom: 0;">
                                    <thead>
                                        <tr>
                                            <th>#</th>
                                            <th>剧集名称</th>
                                            <th>视频数</th>
                                            <th>总播放</th>
                                            <th>账号数</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="(row, idx) in trafficDramas" :key="row.drama_link + '-' + idx">
                                            <td>{{ idx + 1 }}</td>
                                            <td :title="row.drama_link">{{ row.drama_link }}</td>
                                            <td>{{ row.post_count }}</td>
                                            <td>{{ row.total_views }}</td>
                                            <td>{{ row.account_count }}</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                            <div v-else class="empty-state" style="padding: 24px 0;">暂无剧集排行（需描述以剧集链接开头）</div>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    `,
    setup(props, { emit }) {
        const dashboard = ref(null);
        const traffic = ref(null);
        const loading = ref(false);
        const trafficRefreshing = ref(false);
        const error = ref('');
        let timer = null;
        let trafficPollTimer = null;

        const trafficAccounts = computed(() => traffic.value?.accounts || []);
        const trafficDramas = computed(() => traffic.value?.dramas || []);
        const queuePending = computed(() => Number(dashboard.value?.queue?.pending || 0));
        const queueRunning = computed(() => Boolean(dashboard.value?.queue?.current));

        const notify = (message, type = 'info') => {
            emit('notify', { message, type });
        };

        const loadDashboard = async () => {
            loading.value = true;
            error.value = '';
            try {
                dashboard.value = await props.api.getDashboard();
            } catch (err) {
                error.value = getErrorMessage(err);
            } finally {
                loading.value = false;
            }
        };

        const loadTraffic = async () => {
            try {
                traffic.value = await props.api.getDashboardTraffic();
            } catch (err) {
                // 流量缓存失败不阻断概览主区
                console.warn('load traffic failed', err);
            }
        };

        const stopTrafficPoll = () => {
            if (trafficPollTimer) {
                clearInterval(trafficPollTimer);
                trafficPollTimer = null;
            }
        };

        const startTrafficPoll = () => {
            stopTrafficPoll();
            let ticks = 0;
            // 多账号无头浏览器刷新可能很长：约 30 分钟（900 * 2s）
            const maxTicks = 900;
            trafficPollTimer = setInterval(async () => {
                ticks += 1;
                try {
                    await loadTraffic();
                    if (traffic.value?.is_refreshing) {
                        trafficRefreshing.value = true;
                        if (ticks < maxTicks) return;
                        // 超时停轮询并解锁按钮；后台若仍在跑，稍后回概览会自动续轮询
                        stopTrafficPoll();
                        trafficRefreshing.value = false;
                        notify('流量刷新耗时较长，可稍后回到概览查看或再次刷新', 'warning');
                        return;
                    }
                    stopTrafficPoll();
                    trafficRefreshing.value = false;
                    if (traffic.value?.last_error) {
                        notify(traffic.value.last_error, 'error');
                    } else if (traffic.value?.refreshed_at) {
                        notify(
                            `流量刷新完成：账号 ${trafficAccounts.value.length}，剧集 ${trafficDramas.value.length}`,
                            'success'
                        );
                    }
                } catch (e) {
                    if (ticks >= maxTicks) {
                        stopTrafficPoll();
                        trafficRefreshing.value = false;
                        notify('流量刷新状态查询失败', 'error');
                    }
                }
            }, 2000);
        };

        const refreshTraffic = async () => {
            if (trafficRefreshing.value || traffic.value?.is_refreshing) return;
            trafficRefreshing.value = true;
            try {
                const res = await props.api.refreshDashboardTraffic(24);
                if (res.status === 'error') {
                    trafficRefreshing.value = false;
                    notify(res.message || '启动刷新失败', 'error');
                    return;
                }
                notify(res.message || '流量刷新已在后台启动', 'info');
                // 立即拉一次快照（标记 is_refreshing），再轮询直到完成
                await loadTraffic();
                startTrafficPoll();
            } catch (err) {
                trafficRefreshing.value = false;
                notify(getErrorMessage(err), 'error');
            }
        };

        const formatTrafficTime = (iso) => {
            if (!iso) return '-';
            try {
                return new Date(iso).toLocaleString();
            } catch (_) {
                return iso;
            }
        };

        const statusCount = (stats, key) => Number(stats?.[key] || 0);

        onMounted(async () => {
            await Promise.all([loadDashboard(), loadTraffic()]);
            timer = setInterval(loadDashboard, 10000);
            // 仅展示缓存；若上次手动刷新仍在后台跑，则续上轮询
            if (traffic.value?.is_refreshing) {
                trafficRefreshing.value = true;
                startTrafficPoll();
            }
        });
        onBeforeUnmount(() => {
            if (timer) clearInterval(timer);
            stopTrafficPoll();
        });

        return {
            dashboard,
            traffic,
            trafficAccounts,
            trafficDramas,
            queuePending,
            queueRunning,
            loading,
            trafficRefreshing,
            error,
            loadDashboard,
            refreshTraffic,
            formatTrafficTime,
            statusCount
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
                appNotify(`单次最多支持 ${MAX_BATCH_ITEMS} 条下载任务`, 'warning');
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
            const ok = await appConfirm({
                title: '删除视频',
                message: '确定要删除这个视频吗？',
                confirmText: '确定删除',
            });
            if (!ok) return;
            try {
                await props.api.deleteVideo(videoId);
                reload();
                appNotify('视频已删除', 'success');
            } catch (error) {
                appNotify('删除失败: ' + (error.message || error), 'error');
            }
        };

        const deleteSelected = async () => {
            if (selectedIds.value.length === 0) return;
            const ok = await appConfirm({
                title: '批量删除视频',
                message: `确定要删除选中的 ${selectedIds.value.length} 个视频吗？`,
                confirmText: '确定删除',
            });
            if (!ok) return;

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
                appNotify('批量删除失败: ' + (error.message || error), 'error');
            }
        };

        const openVideo = async (videoId) => {
            try {
                await props.api.openVideo(videoId);
            } catch (error) {
                appNotify('打开视频失败: ' + (error.message || error), 'error');
            }
        };

        const openVideoFolder = async (videoId) => {
            try {
                await props.api.openVideoFolder(videoId);
            } catch (error) {
                appNotify('打开文件夹失败: ' + (error.message || error), 'error');
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
                appNotify('复制路径失败: ' + (error.message || error), 'error');
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
            </div>

            <!-- 视频号配置 -->
            <div class="card">
                <div class="card-title">视频号配置</div>

                <div class="form-group">
                    <label>上传超时时间 (秒)</label>
                    <input
                        v-model.number="formData.weixin_upload_timeout"
                        type="number"
                        min="60"
                        max="3600"
                    />
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        视频上传和发表按钮等待的超时时间，默认 600 秒（10 分钟）
                    </p>
                </div>

                <div class="form-group">
                    <label>连续上传间隔 (秒)</label>
                    <input
                        v-model.number="formData.weixin_inter_upload_cooldown"
                        type="number"
                        min="0"
                        max="300"
                    />
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        批量上传时，两个视频之间的等待间隔，默认 20 秒
                    </p>
                </div>

                <div class="form-group">
                    <label>视频号最大重试次数</label>
                    <input
                        v-model.number="formData.weixin_max_retries"
                        type="number"
                        min="1"
                        max="10"
                    />
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        视频号上传失败时的重试次数
                    </p>
                </div>
            </div>

            <!-- 视频号上传代理（独立卡片） — 已迁移到「视频号上传管理 → 发布位置管理」tab；
                 此卡片仅作为兼容保留，UI 隐藏，formData 字段保留避免 PUT settings 形状变化 -->
            <div v-if="false" class="card">
                <div class="card-title">📡 视频号上传代理</div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" v-model="formData.weixin_proxy_enabled" />
                        启用上传代理
                    </label>
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        开启后，登录扫码、Cookie 校验、视频上传等所有浏览器流量都会走下方代理。
                        仅支持本地无鉴权代理（如爱加速"手动代理 HTTP/Socks5"模式提供的本地端口）。
                    </p>
                </div>

                <div class="row">
                    <div class="col">
                        <div class="form-group">
                            <label>协议</label>
                            <select v-model="formData.weixin_proxy_scheme">
                                <option value="http">HTTP</option>
                                <option value="socks5">Socks5</option>
                            </select>
                        </div>
                    </div>
                    <div class="col">
                        <div class="form-group">
                            <label>主机</label>
                            <input v-model.trim="formData.weixin_proxy_host" placeholder="127.0.0.1" />
                        </div>
                    </div>
                    <div class="col">
                        <div class="form-group">
                            <label>端口</label>
                            <input v-model.number="formData.weixin_proxy_port" type="number" min="0" max="65535" placeholder="例如 30001" />
                        </div>
                    </div>
                </div>

                <div class="form-group">
                    <label>位置策略</label>
                    <select v-model="formData.weixin_location_mode">
                        <option value="proxy_ip">按代理出口 IP 自动识别位置</option>
                        <option value="hidden">不显示位置（始终选「不显示位置」）</option>
                    </select>
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        选择「按代理 IP 自动识别」时，视频号会根据代理出口 IP 显示对应地区；
                        选择「不显示位置」时，发表时会强制选中位置列表第一项。
                    </p>
                </div>

                <div class="form-group">
                    <button class="btn btn-secondary" @click="testProxy" :disabled="isTestingProxy">
                        {{ isTestingProxy ? '检测中...' : '🔍 测试代理位置' }}
                    </button>
                    <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                        会先保存当前设置，再实测代理出口 IP / 归属地（绕过缓存）。
                    </p>
                    <p v-if="proxyTestResult" :class="['text-muted', proxyTestOk ? 'text-success' : 'text-danger']" style="font-size: 12px; margin-top: 8px; white-space: pre-line;">
                        {{ proxyTestResult }}
                    </p>
                </div>
            </div>

            <!-- 维护清理 -->
            <div class="card">
                <div class="card-title">🧹 维护清理</div>
                <p class="text-muted" style="font-size: 13px; margin-bottom: 12px;">
                    清理不会删除账号、账号 Cookie 或本地视频文件；上传中的任务会自动保留。
                </p>
                <div class="form-group">
                    <label>
                        <input type="checkbox" v-model="cleanupForm.logs" />
                        清除日志
                    </label>
                    <p class="text-muted" style="font-size: 12px; margin-top: 4px;">
                        清空实时日志视图和打包版 app.log。
                    </p>
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" v-model="cleanupForm.cache" />
                        清除缓存
                    </label>
                    <p class="text-muted" style="font-size: 12px; margin-top: 4px;">
                        清理代理检测缓存、临时浏览器 Profile、素材索引缓存；不删除下载的视频文件。
                    </p>
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" v-model="cleanupForm.upload_history" />
                        清除历史视频上传记录
                    </label>
                    <p class="text-muted" style="font-size: 12px; margin-top: 4px;">
                        删除发布情况里的历史任务记录，正在上传/发布中的任务会跳过。
                    </p>
                </div>
                <button class="btn btn-danger" @click="runCleanup" :disabled="isCleaning">
                    <span v-if="isCleaning"><span class="spinner"></span> 清理中...</span>
                    <span v-else>执行清理</span>
                </button>
                <p v-if="cleanupResult" class="text-muted" style="font-size: 12px; margin-top: 10px; white-space: pre-line;">
                    {{ cleanupResult }}
                </p>
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
                            1.0.0
                        </div>
                    </div>
                </div>
            </div>

            <!-- 保存按钮：作用于以上全部卡片的设置 -->
            <button class="btn btn-primary btn-block" @click="save">
                💾 保存设置
            </button>
        </div>
    `,

    setup(props, { emit }) {
        const formData = reactive({
            video_dir: props.settings.video_dir,
            download_timeout: props.settings.download_timeout,
            max_retries: props.settings.max_retries,
            weixin_upload_timeout: props.settings.weixin_upload_timeout || 600,
            weixin_inter_upload_cooldown: props.settings.weixin_inter_upload_cooldown || 30,
            weixin_max_retries: props.settings.weixin_max_retries || 3,
            weixin_proxy_enabled: !!props.settings.weixin_proxy_enabled,
            weixin_proxy_scheme: props.settings.weixin_proxy_scheme || 'http',
            weixin_proxy_host: props.settings.weixin_proxy_host || '127.0.0.1',
            weixin_proxy_port: props.settings.weixin_proxy_port || 0,
            weixin_location_mode: props.settings.weixin_location_mode || 'proxy_ip'
        });
        const isBrowsing = ref(false);
        const isTestingProxy = ref(false);
        const proxyTestResult = ref('');
        const proxyTestOk = ref(false);
        const cleanupForm = reactive({
            logs: true,
            cache: true,
            upload_history: true
        });
        const isCleaning = ref(false);
        const cleanupResult = ref('');

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
                appNotify('选择目录失败: ' + (error.message || error), 'error');
            } finally {
                isBrowsing.value = false;
            }
        };

        const save = async () => {
            try {
                emit('save', formData);
            } catch (error) {
                appNotify('保存失败: ' + (error.message || error), 'error');
            }
        };

        const testProxy = async () => {
            if (isTestingProxy.value) return;
            proxyTestResult.value = '';
            proxyTestOk.value = false;
            isTestingProxy.value = true;
            try {
                // 先把当前表单里的代理配置保存到后端，再测 —— 避免「我刚改了端口但还没点保存」的混淆。
                await props.api.updateSettings(formData);
                const result = await props.api.testWeixinProxy();
                if (result.status === 'success') {
                    const r = result.result || {};
                    const proxy = r.proxy || {};
                    const location = [proxy.country, proxy.region, proxy.city].filter(Boolean).join(' ');
                    const lines = [
                        `✅ 代理生效：${proxy.ip || '-'}  ${location || '位置未知'}`,
                        `   归属：${proxy.isp || '-'}（检测源：${proxy.provider || '-'}）`,
                    ];
                    if (r.direct_failed) {
                        lines.push('⚠️ 直连 IP 无法获取，未能独立验证代理出口（若整机走 VPN，请忽略）');
                    } else if (r.direct?.ip) {
                        lines.push(`   对比直连 IP：${r.direct.ip}（不同，代理已生效）`);
                    }
                    proxyTestResult.value = lines.join('\n');
                    proxyTestOk.value = true;
                } else {
                    proxyTestResult.value = `❌ 测试失败：${result.message || '代理不可用'}`;
                    proxyTestOk.value = false;
                }
            } catch (error) {
                proxyTestResult.value = '❌ 测试失败：' + (error.detail || error.message || error);
                proxyTestOk.value = false;
            } finally {
                isTestingProxy.value = false;
            }
        };

        const runCleanup = async () => {
            if (isCleaning.value) return;
            if (!cleanupForm.logs && !cleanupForm.cache && !cleanupForm.upload_history) {
                appNotify('请至少选择一个清理项', 'warning');
                return;
            }
            const items = [];
            if (cleanupForm.logs) items.push('日志');
            if (cleanupForm.cache) items.push('缓存');
            if (cleanupForm.upload_history) items.push('历史视频上传记录');
            const ok = await appConfirm({
                title: '清理确认',
                message: `确定清理：${items.join('、')}？\n\n不会删除账号、Cookie 或本地视频文件。`,
                confirmText: '确定清理',
            });
            if (!ok) return;

            isCleaning.value = true;
            cleanupResult.value = '';
            try {
                const res = await props.api.cleanupMaintenance({ ...cleanupForm });
                const result = res.result || {};
                const lines = ['清理完成'];
                if (result.logs) {
                    lines.push(`日志：清除内存记录 ${result.logs.memory_entries || 0} 条，日志文件 ${result.logs.files?.length || 0} 个`);
                }
                if (result.cache) {
                    lines.push(`缓存：清理目录 ${result.cache.removed_paths?.length || 0} 个，素材索引 ${result.cache.video_index_rows || 0} 条`);
                }
                if (result.upload_history) {
                    lines.push(`历史上传记录：删除 ${result.upload_history.deleted || 0} 条，跳过活动任务 ${result.upload_history.skipped_active || 0} 条`);
                }
                cleanupResult.value = lines.join('\n');
            } catch (error) {
                cleanupResult.value = '清理失败：' + getErrorMessage(error);
            } finally {
                isCleaning.value = false;
            }
        };

        return {
            formData,
            isBrowsing,
            isTestingProxy,
            proxyTestResult,
            proxyTestOk,
            cleanupForm,
            isCleaning,
            cleanupResult,
            browseVideoDir,
            save,
            testProxy,
            runCleanup
        };
    }
});

// ============================================================================
// 微信视频号上传页面组件
// ============================================================================

app.component('weixin-page', {
    props: ['api', 'initialTab'],
    template: `
        <div :class="['weixin-shell', { 'account-mode': tab === 'accounts' }]">
            <div class="header weixin-header">
                <div>
                    <div class="header-eyebrow">CHANNELS WORKSPACE</div>
                    <h1>{{ tab === 'accounts' ? '视频号账号管理' : (tab === 'proxies' ? '代理与位置' : '视频号发布中心') }}</h1>
                    <p>{{ tab === 'accounts' ? '集中管理账号、内容发布与发布记录' : (tab === 'proxies' ? '管理发布代理与常用位置' : '创建并跟踪视频号发布任务') }}</p>
                </div>
            </div>

            <!-- 消息提示 -->
            <div v-if="message.show" :class="['alert', 'alert-' + message.type]">
                {{ message.text }}
            </div>

            <div v-if="false && loginModal.show" class="modal-overlay" @click.self="cancelEmbeddedLogin">
                <div class="modal-box">
                    <div class="modal-header">
                        <h3>应用内扫码登录</h3>
                        <button class="modal-close" @click="cancelEmbeddedLogin">×</button>
                    </div>
                    <div style="text-align: center;">
                        <p class="text-muted" style="margin-bottom: 12px;">{{ loginModal.message || '正在加载二维码...' }}</p>
                        <div v-if="loginModal.qr" style="display: inline-block; padding: 14px; background: #fff; border-radius: 12px; border: 1px solid #ddd;">
                            <img :src="'data:image/png;base64,' + loginModal.qr" style="width: 240px; max-width: 100%; display: block;" />
                        </div>
                        <div v-else class="card" style="margin: 0 auto; max-width: 280px;">
                            <span class="spinner"></span> 正在获取二维码...
                        </div>
                        <p class="text-muted" style="font-size: 12px; margin-top: 12px;">
                            不会弹出外部视频号登录页面；请用微信扫描上方二维码。
                        </p>
                        <div class="action-group" style="justify-content: center; margin-top: 16px;">
                            <button class="btn btn-secondary" @click="cancelEmbeddedLogin">取消</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 标签页 -->
            <div v-if="tab !== 'accounts'" class="tabs">
                <div :class="['tab', { active: tab === 'accounts' }]" @click="tab = 'accounts'">账号管理</div>
                <div :class="['tab', { active: tab === 'proxies' }]" @click="tab = 'proxies'; loadProxyProfiles(); loadFavoriteLocations()">代理与位置</div>
            </div>

            <!-- 账号管理 -->
            <div v-if="tab === 'accounts'" class="account-workspace">
                <aside class="account-list-panel">
                    <div class="account-list-header">
                        <div>
                            <div class="account-list-kicker">账号中心</div>
                            <div class="account-list-title">视频号账号</div>
                            <div v-if="refreshAllState.is_refreshing" class="account-refresh-hint">
                                正在批量刷新账号状态…
                            </div>
                        </div>
                        <div class="account-list-actions">
                            <button
                                class="icon-button"
                                :class="{ 'is-loading': refreshAllState.is_refreshing }"
                                @click="triggerRefreshAll"
                                :disabled="refreshAllState.is_refreshing"
                                title="刷新账号状态"
                            >
                                <span class="refresh-icon">↻</span>
                            </button>
                            <button
                                class="account-add-button"
                                @click="addAccount"
                                :disabled="refreshAllState.is_refreshing || addingAccount"
                            >{{ addingAccount ? '添加中...' : '＋ 添加' }}</button>
                        </div>
                    </div>
                    <div class="account-list" v-if="accounts.length">
                        <div
                            v-for="acc in accounts"
                            :key="acc.id"
                            :class="['account-list-item', { active: selectedAccount && selectedAccount.id === acc.id }]"
                            @click="selectAccount(acc)"
                        >
                            <input
                                type="checkbox"
                                class="account-select-checkbox"
                                :checked="selectedAccountIds.includes(acc.id)"
                                @click.stop
                                @change="toggleAccountSelect(acc.id, $event.target.checked)"
                            />
                            <span class="account-avatar">
                                <img v-if="acc.avatar_url" :src="acc.avatar_url" :alt="acc.name" />
                                <template v-else>{{ (acc.name || '?').slice(0, 1).toUpperCase() }}</template>
                            </span>
                            <span class="account-list-copy">
                                <span class="account-list-name">{{ acc.name }}</span>
                                <span class="account-list-meta">{{ acc.status === 'active' ? '已连接' : getStatusText(acc.status) }}</span>
                            </span>
                            <span :class="['account-status-dot', getStatusClass(acc.status)]"></span>
                        </div>
                    </div>
                    <table class="table legacy-account-table" v-if="accounts.length">
                        <thead>
                            <tr>
                                <th style="width: 36px;">
                                    <input
                                        type="checkbox"
                                        :checked="isAllAccountsSelected"
                                        :indeterminate.prop="isPartiallyAccountsSelected"
                                        @change="toggleSelectAllAccounts"
                                        :disabled="refreshAllState.is_refreshing"
                                    />
                                </th>
                                <th>ID</th>
                                <th>名称</th>
                                <th>状态</th>
                                <th>备注</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="acc in accounts"
                                :key="acc.id"
                                :class="{ selected: selectedAccount && selectedAccount.id === acc.id }"
                                @click="selectAccount(acc)"
                                style="cursor: pointer;"
                            >
                                <td @click.stop>
                                    <input
                                        type="checkbox"
                                        :checked="selectedAccountIds.includes(acc.id)"
                                        @change="toggleAccountSelect(acc.id, $event.target.checked)"
                                        :disabled="refreshAllState.is_refreshing"
                                    />
                                </td>
                                <td>{{ acc.id }}</td>
                                <td>{{ acc.name }}</td>
                                <td><span :class="'badge badge-' + getStatusClass(acc.status)">{{ getStatusText(acc.status) }}</span></td>
                                <td>
                                    <span v-if="acc.status === 'expired' || acc.status === 'error'" style="color: #ff4d4f; font-size: 13px;">需重新登录</span>
                                    <span v-else style="color: #999; font-size: 13px;">-</span>
                                </td>
                                <td>{{ formatDate(acc.created_at) }}</td>
                                <td>
                                    <div class="action-group">
                                        <button class="btn btn-primary btn-small" @click.stop="loginAccount(acc.id)" :disabled="acc.status === 'logging_in' || refreshAllState.is_refreshing">
                                            {{ acc.status === 'logging_in' ? '扫码中...' : '扫码登录' }}
                                        </button>
                                        <button class="btn btn-secondary btn-small" @click.stop="refreshAccount(acc.id)" :disabled="refreshingIds.has(acc.id) || refreshAllState.is_refreshing">
                                            <span v-if="refreshingIds.has(acc.id)"><span class="spinner"></span> 刷新中</span>
                                            <span v-else>刷新</span>
                                        </button>
                                        <button v-if="false" class="btn btn-secondary btn-small" @click.stop="openWeixinPostList(acc.id)" :disabled="refreshAllState.is_refreshing">
                                            视频管理页
                                        </button>
                                        <button class="btn btn-danger btn-small" @click.stop="openDeleteAccount(acc)" :disabled="refreshAllState.is_refreshing">删除</button>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    <div v-else class="account-list-empty">
                        <span>暂无账号</span>
                        <button class="text-button" @click="showAddAccount = true">添加第一个账号</button>
                    </div>
                    <div class="account-list-footer">
                        <span class="account-list-count">{{ accounts.length }} 个账号</span>
                        <div class="account-list-footer-actions">
                            <button
                                v-if="accounts.length"
                                class="text-button"
                                @click="toggleSelectAllAccounts"
                                :disabled="refreshAllState.is_refreshing"
                            >{{ isAllAccountsSelected ? '取消全选' : '全选' }}</button>
                            <button
                                class="btn btn-danger btn-small"
                                @click="openBatchDeleteAccounts"
                                :disabled="!selectedAccountIds.length || refreshAllState.is_refreshing || accountDeleteModal.busy"
                                title="删除所选账号"
                            >删除所选{{ selectedAccountIds.length ? (' (' + selectedAccountIds.length + ')') : '' }}</button>
                        </div>
                    </div>
                </aside>

                <main v-if="selectedAccount" class="account-main-panel">
                    <div class="account-main-header">
                        <div class="account-heading">
                            <span class="account-heading-avatar">
                                <img v-if="selectedAccount.avatar_url" :src="selectedAccount.avatar_url" :alt="selectedAccount.name" />
                                <template v-else>{{ (selectedAccount.name || '?').slice(0, 1).toUpperCase() }}</template>
                            </span>
                            <div>
                                <div class="account-heading-name">{{ selectedAccount.name }}</div>
                                <div class="account-heading-status">
                                    <span :class="['account-status-dot', getStatusClass(selectedAccount.status)]"></span>
                                    {{ getStatusText(selectedAccount.status) }}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="account-tabs">
                        <button :class="['account-tab', { active: accountDetailTab === 'upload' }]" @click="accountDetailTab = 'upload'">视频上传</button>
                        <button :class="['account-tab', { active: accountDetailTab === 'manage' }]" @click="openAccountManagement">视频号管理</button>
                        <button :class="['account-tab', { active: accountDetailTab === 'status' }]" @click="accountDetailTab = 'status'; loadTasks()">发布记录</button>
                        <button :class="['account-tab', { active: accountDetailTab === 'traffic' }]" @click="accountDetailTab = 'traffic'">视频流量筛选</button>
                    </div>

                    <div v-if="false && accountDetailTab === 'upload'">
                        <p class="text-muted" style="margin-bottom: 12px;">为该账号创建视频发布任务。</p>
                        <button class="btn btn-primary" @click="goAccountUpload(selectedAccount)">进入该账号上传</button>
                    </div>

                    <div v-if="accountDetailTab === 'upload'" class="account-tab-pane content-pane">
                        <div class="pane-heading">
                            <h2>发布视频</h2>
                            <p>选择视频素材并完善发布信息</p>
                        </div>
                        <div class="form-group">
                            <label>视频文件列表</label>
                            <table class="table" style="margin-bottom: 10px;" v-if="batchForm.videoFiles.length">
                                <thead>
                                    <tr>
                                        <th style="width: 85%;">文件路径</th>
                                        <th style="width: 15%;">操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="(file, idx) in batchForm.videoFiles" :key="idx">
                                        <td class="truncate" :title="file">{{ file }}</td>
                                        <td><button class="btn btn-danger btn-small" @click="removeBatchFile(idx)">删除</button></td>
                                    </tr>
                                </tbody>
                            </table>
                            <button class="btn btn-secondary" @click="browseBatchFiles" :disabled="isBrowsingBatchFiles">
                                <span v-if="!isBrowsingBatchFiles">选择文件（可多选）</span>
                                <span v-else>选择中...</span>
                            </button>
                            <p class="text-muted" style="font-size: 12px; margin-top: 5px;">已选 {{ batchForm.videoFiles.length }} 个文件</p>
                        </div>
                        <div class="form-group">
                            <label>视频描述（所有视频共用）</label>
                            <textarea v-model="batchForm.descriptionStr" placeholder="所有视频都会使用该描述" rows="3"></textarea>
                        </div>
                        <div class="form-group">
                            <label>剧集链接（可选）</label>
                            <input v-model="batchForm.drama_link" type="text" placeholder="输入视频号剧集名称或链接">
                        </div>
                        <div class="row">
                            <div class="col">
                                <div class="form-group">
                                    <label>上传代理</label>
                                    <select v-model="batchForm.proxy_profile_id">
                                        <option value="">不指定代理 Profile</option>
                                        <option v-for="p in enabledProxyProfiles" :key="p.id" :value="p.id">{{ proxyProfileOptionLabel(p) }}</option>
                                    </select>
                                </div>
                            </div>
                            <div class="col">
                                <div class="form-group">
                                    <label>发表位置</label>
                                    <div ref="locationComboboxRef" style="position: relative;">
                                        <input
                                            v-model.trim="batchForm.location_label"
                                            type="text"
                                            placeholder="可下拉选择常用位置或手输；留空则按「不显示位置」发表"
                                            style="padding-right: 36px;"
                                            @focus="showLocationDropdown = true"
                                        />
                                        <button
                                            type="button"
                                            @click="showLocationDropdown = !showLocationDropdown"
                                            :title="showLocationDropdown ? '收起' : '展开常用位置'"
                                            style="position: absolute; right: 1px; top: 1px; bottom: 1px; width: 32px;
                                                   background: transparent; border: none; cursor: pointer;
                                                   color: #888; font-size: 12px;"
                                        >{{ showLocationDropdown ? '▲' : '▼' }}</button>
                                        <div
                                            v-if="showLocationDropdown && filteredFavoriteLocations.length"
                                            style="position: absolute; top: calc(100% + 2px); left: 0; right: 0;
                                                   background: #fff; border: 1px solid #ddd; border-radius: 4px;
                                                   box-shadow: 0 2px 8px rgba(0,0,0,0.08); max-height: 220px;
                                                   overflow-y: auto; z-index: 50;"
                                        >
                                            <div
                                                v-for="loc in filteredFavoriteLocations"
                                                :key="loc.id"
                                                @mousedown.prevent="selectFavoriteLocation(loc.name)"
                                                style="padding: 8px 12px; cursor: pointer; font-size: 14px;"
                                                onmouseover="this.style.background='#f5f5f5'"
                                                onmouseout="this.style.background='#fff'"
                                            >{{ loc.name }}</div>
                                        </div>
                                    </div>
                                    <p v-if="!favoriteLocations.length" class="text-muted" style="font-size: 12px; margin-top: 4px;">
                                        可在「代理与位置」页设置常用位置，之后这里会出现下拉候选
                                    </p>
                                </div>
                            </div>
                        </div>
                        <button class="btn btn-success btn-block" @click="createBatchUpload" :disabled="!selectedAccount || batchForm.videoFiles.length === 0">
                            为 {{ selectedAccount.name }} 创建上传任务
                        </button>
                    </div>

                    <div v-if="accountDetailTab === 'manage'" class="account-tab-pane manage-pane">
                        <div class="pane-toolbar">
                            <div>
                                <h2>视频号管理</h2>
                                <p>登录后可管理当前账号的视频号内容</p>
                            </div>
                            <div class="action-group">
                            <button
                                v-if="selectedAccount.status !== 'active'"
                                class="btn btn-primary"
                                @click="startNativeWeixinBrowser(true)"
                                :disabled="refreshAllState.is_refreshing"
                            >登录视频号</button>
                            <button
                                v-else
                                class="btn btn-primary"
                                @click="reloadNativeWeixinBrowser"
                                :disabled="refreshAllState.is_refreshing"
                            >重新加载页面</button>
                            <button class="btn btn-secondary" @click="refreshAccount(selectedAccount.id)" :disabled="refreshingIds.has(selectedAccount.id) || refreshAllState.is_refreshing">刷新状态</button>
                            <button class="btn btn-danger" @click="openDeleteAccount(selectedAccount)" :disabled="refreshAllState.is_refreshing">删除账号</button>
                            </div>
                        </div>
                        <div v-if="selectedAccount.status !== 'active' && !nativeBrowserVisible" class="account-expired-state">
                            <div class="account-expired-icon">!</div>
                            <h3>账号登录已过期</h3>
                            <p>请重新登录后继续管理视频号内容</p>
                            <button class="btn btn-primary" @click="startNativeWeixinBrowser(true)">登录视频号</button>
                        </div>
                        <div v-else class="native-browser-shell">
                            <div class="browser-frame-header">
                                <div class="browser-controls"><span></span><span></span><span></span></div>
                                <div class="browser-address">{{ selectedAccount.status === 'active' ? 'https://channels.weixin.qq.com/platform' : 'https://channels.weixin.qq.com/login.html' }}</div>
                                <div class="native-browser-actions">
                                    <button class="text-button" @click="backNativeWeixinBrowser">后退</button>
                                    <button class="text-button" @click="reloadNativeWeixinBrowser">刷新</button>
                                </div>
                            </div>
                            <div ref="browserHostRef" class="native-browser-host">
                                <div v-if="!hasNativeBrowser" class="native-browser-placeholder">
                                    <span class="spinner"></span>
                                    <p>正在加载视频号管理页面...</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-if="accountDetailTab === 'status'" class="account-tab-pane content-pane">
                        <div class="pane-toolbar">
                            <div>
                                <h2>发布记录</h2>
                                <p>查看 {{ selectedAccount.name }} 的视频发布进度与结果</p>
                            </div>
                            <div class="action-group">
                                <span v-if="selectedTaskIds.length" class="text-muted">已选 {{ selectedTaskIds.length }} 项</span>
                                <button class="btn btn-danger btn-small" :disabled="!selectedTaskIds.length" @click="deleteSelectedTasks">删除选中</button>
                                <button class="btn btn-secondary btn-small" @click="loadTasks">刷新</button>
                            </div>
                        </div>
                        <div v-if="selectedAccountTasks.length" class="account-task-table-wrap">
                        <table class="table account-task-table">
                            <thead>
                                <tr>
                                    <th style="width: 36px;">
                                        <input
                                            type="checkbox"
                                            :checked="isAllSelectableSelected"
                                            :indeterminate.prop="isPartiallySelected"
                                            :disabled="!selectableTaskIds.length"
                                            @change="toggleSelectAllTasks($event.target.checked)"
                                        />
                                    </th>
                                    <th>视频</th>
                                    <th>描述</th>
                                    <th>位置</th>
                                    <th>状态</th>
                                    <th>创建时间</th>
                                    <th>错误</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="task in selectedAccountTasks" :key="task.id">
                                    <td>
                                        <input
                                            type="checkbox"
                                            :value="task.id"
                                            v-model="selectedTaskIds"
                                            :disabled="isTaskActive(task.status)"
                                        />
                                    </td>
                                    <td :title="task.video_path">{{ getFileName(task.video_path) }}</td>
                                    <td>{{ task.description || task.title || task.video_path }}</td>
                                    <td>{{ task.location_label || '-' }}</td>
                                    <td><span :class="'badge badge-' + getTaskStatusClass(task.status)">{{ getTaskStatusText(task.status) }}</span></td>
                                    <td>{{ formatDate(task.created_at) }}</td>
                                    <td>{{ task.error_msg || '-' }}</td>
                                    <td>
                                        <div class="action-group">
                                            <button v-if="task.status === 'failed'" class="btn btn-primary btn-small" @click="retryTask(task.id)">重试</button>
                                            <button class="btn btn-danger btn-small" :disabled="isTaskActive(task.status)" @click="deleteTask(task.id)">删除</button>
                                        </div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                        </div>
                        <div v-else class="empty-state">该账号暂无发布记录</div>
                    </div>

                    <div v-if="accountDetailTab === 'traffic'" class="account-tab-pane content-pane">
                        <div class="pane-toolbar">
                            <div>
                                <h2>视频流量筛选</h2>
                                <p>筛选发表超过观察期且播放量低于阈值的视频，勾选后删除。</p>
                            </div>
                            <div class="action-group">
                                <span v-if="selectedTrafficIds.length" class="text-muted">已选 {{ selectedTrafficIds.length }} 项</span>
                                <button
                                    class="btn btn-danger btn-small"
                                    :disabled="!selectedTrafficIds.length || trafficDeleting || trafficScanning"
                                    @click="deleteSelectedTrafficPosts"
                                >{{ trafficDeleting ? '删除中...' : '删除选中' }}</button>
                            </div>
                        </div>
                        <div class="traffic-filter-form row">
                            <div class="col">
                                <div class="form-group">
                                    <label>观察期（小时）</label>
                                    <input v-model.number="trafficFilter.grace_period_hours" type="number" min="0" step="1">
                                </div>
                            </div>
                            <div class="col">
                                <div class="form-group">
                                    <label>播放量低于</label>
                                    <input v-model.number="trafficFilter.min_views" type="number" min="0" step="1">
                                </div>
                            </div>
                            <div class="col" style="display:flex;align-items:flex-end;">
                                <div class="form-group" style="width:100%;">
                                    <label>&nbsp;</label>
                                    <button
                                        class="btn btn-primary btn-block"
                                        :disabled="trafficScanning || !selectedAccount || selectedAccount.status !== 'active'"
                                        @click="scanTrafficCandidates"
                                    >{{ trafficScanning ? '后台扫描中...' : '扫描候选' }}</button>
                                </div>
                            </div>
                        </div>
                        <p class="text-muted" style="font-size:12px;margin-bottom:14px;">
                            扫描在后台执行，可继续操作其它页面。
                            <span v-if="trafficScanMeta.scanned != null">最近扫描：作品 {{ trafficScanMeta.scanned }}，候选 {{ trafficCandidates.length }}。</span>
                        </p>
                        <div v-if="trafficCandidates.length" class="account-task-table-wrap">
                            <table class="table account-task-table">
                                <thead>
                                    <tr>
                                        <th style="width:36px;">
                                            <input
                                                type="checkbox"
                                                :checked="isAllTrafficSelected"
                                                :indeterminate.prop="isPartiallyTrafficSelected"
                                                @change="toggleSelectAllTraffic($event.target.checked)"
                                            />
                                        </th>
                                        <th>标题</th>
                                        <th>发布时间</th>
                                        <th>播放量</th>
                                        <th>命中原因</th>
                                        <th>操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="item in trafficCandidates" :key="item.post_id">
                                        <td>
                                            <input type="checkbox" :value="item.post_id" v-model="selectedTrafficIds" />
                                        </td>
                                        <td :title="item.title">{{ item.title || item.post_id }}</td>
                                        <td>{{ formatDate(item.published_at) }}</td>
                                        <td>{{ item.view_count == null ? '-' : item.view_count }}</td>
                                        <td>
                                            <span
                                                v-for="reason in item.reasons"
                                                :key="reason"
                                                class="badge"
                                                :class="reason === 'low_views' ? 'badge-warning' : 'badge-pending'"
                                                style="margin-right:4px;"
                                            >{{ trafficReasonText(reason) }}</span>
                                        </td>
                                        <td>
                                            <button
                                                class="btn btn-danger btn-small"
                                                :disabled="trafficDeleting"
                                                @click="deleteOneTrafficPost(item)"
                                            >删除</button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <div v-else class="empty-state">
                            {{ trafficScannedOnce ? '暂无符合条件的候选视频' : '设置筛选条件后点击「扫描候选」' }}
                        </div>
                    </div>
                </main>

                <main v-else class="account-main-panel account-empty-panel">
                    <div class="account-empty-content">
                        <div class="account-empty-icon">◎</div>
                        <h2>选择一个视频号账号</h2>
                        <p>从左侧账号列表选择账号后开始管理</p>
                    </div>
                </main>
            </div>

            <!-- 批量上传 -->
            <div v-if="tab === 'batch'">
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
                        <label>视频文件列表</label>
                        <table class="table" style="margin-bottom: 10px;" v-if="batchForm.videoFiles.length">
                            <thead>
                                <tr>
                                    <th style="width: 85%;">文件路径</th>
                                    <th style="width: 15%;">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(file, idx) in batchForm.videoFiles" :key="idx">
                                    <td class="truncate" :title="file">{{ file }}</td>
                                    <td>
                                        <button class="btn btn-danger btn-small" @click="removeBatchFile(idx)">删除</button>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                        <div class="row">
                            <button class="btn btn-secondary" @click="browseBatchFiles" :disabled="isBrowsingBatchFiles">
                                <span v-if="!isBrowsingBatchFiles">选择文件（可多选）</span>
                                <span v-else>选择中...</span>
                            </button>
                        </div>
                        <p class="text-muted" style="font-size: 12px; margin-top: 5px;">
                            已选 {{ batchForm.videoFiles.length }} 个文件
                        </p>
                    </div>
                    <div class="form-group">
                        <label>视频描述（所有视频共用）</label>
                        <textarea v-model="batchForm.descriptionStr" placeholder="所有视频都会使用该描述" rows="3"></textarea>
                    </div>
                    <div class="form-group">
                        <label>剧集链接（可选）</label>
                        <input v-model="batchForm.drama_link" type="text" placeholder="输入视频号剧集名称">
                    </div>
                    <div class="row">
                        <div class="col">
                            <div class="form-group">
                                <label>上传代理</label>
                                <!-- 与「发表位置」同款 combobox 风格的下拉。代理只能从已配置的 enabled
                                     profile 里选，不允许自定义输入，所以展示框做成只读外观（光标 pointer）。 -->
                                <div ref="proxyComboboxRef" style="position: relative;">
                                    <div
                                        @click="showProxyDropdown = !showProxyDropdown"
                                        :title="selectedProxyDisplay"
                                        style="border: 1px solid #d9d9d9; border-radius: 4px;
                                               padding: 8px 36px 8px 12px; cursor: pointer;
                                               background: #fff; font-size: 14px; line-height: 1.5;
                                               min-height: 38px; white-space: nowrap; overflow: hidden;
                                               text-overflow: ellipsis; user-select: none;"
                                    >{{ selectedProxyDisplay }}</div>
                                    <button
                                        type="button"
                                        @click.stop="showProxyDropdown = !showProxyDropdown"
                                        :title="showProxyDropdown ? '收起' : '展开代理列表'"
                                        style="position: absolute; right: 1px; top: 1px; bottom: 1px; width: 32px;
                                               background: transparent; border: none; cursor: pointer;
                                               color: #888; font-size: 12px;"
                                    >{{ showProxyDropdown ? '▲' : '▼' }}</button>
                                    <div
                                        v-if="showProxyDropdown"
                                        style="position: absolute; top: calc(100% + 2px); left: 0; right: 0;
                                               background: #fff; border: 1px solid #ddd; border-radius: 4px;
                                               box-shadow: 0 2px 8px rgba(0,0,0,0.08); max-height: 220px;
                                               overflow-y: auto; z-index: 50;"
                                    >
                                        <div
                                            @mousedown.prevent="selectProxyProfile('')"
                                            style="padding: 8px 12px; cursor: pointer; font-size: 14px; color: #999;"
                                            onmouseover="this.style.background='#f5f5f5'"
                                            onmouseout="this.style.background='#fff'"
                                        >不指定代理 Profile</div>
                                        <div
                                            v-for="p in enabledProxyProfiles"
                                            :key="p.id"
                                            @mousedown.prevent="selectProxyProfile(p.id)"
                                            style="padding: 8px 12px; cursor: pointer; font-size: 14px;"
                                            onmouseover="this.style.background='#f5f5f5'"
                                            onmouseout="this.style.background='#fff'"
                                        >{{ proxyProfileOptionLabel(p) }}</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col">
                            <div class="form-group">
                                <label>发表位置</label>
                                <!-- 自定义 combobox：原生 <datalist> 在 Chromium 上没有可见的下拉箭头，
                                     UX 不够明显。这里在 input 右侧放一个明确的 ▼ 按钮，点击后展示候选浮层；
                                     输入文字会自动过滤候选；点候选项填入 input 并关闭浮层。 -->
                                <div ref="locationComboboxRef" style="position: relative;">
                                    <input
                                        v-model.trim="batchForm.location_label"
                                        type="text"
                                        placeholder="可下拉选择常用位置或手输；留空则按「不显示位置」发表"
                                        style="padding-right: 36px;"
                                        @focus="showLocationDropdown = true"
                                    />
                                    <button
                                        type="button"
                                        @click="showLocationDropdown = !showLocationDropdown"
                                        :title="showLocationDropdown ? '收起' : '展开常用位置'"
                                        style="position: absolute; right: 1px; top: 1px; bottom: 1px; width: 32px;
                                               background: transparent; border: none; cursor: pointer;
                                               color: #888; font-size: 12px;"
                                    >{{ showLocationDropdown ? '▲' : '▼' }}</button>
                                    <div
                                        v-if="showLocationDropdown && filteredFavoriteLocations.length"
                                        style="position: absolute; top: calc(100% + 2px); left: 0; right: 0;
                                               background: #fff; border: 1px solid #ddd; border-radius: 4px;
                                               box-shadow: 0 2px 8px rgba(0,0,0,0.08); max-height: 220px;
                                               overflow-y: auto; z-index: 50;"
                                    >
                                        <div
                                            v-for="loc in filteredFavoriteLocations"
                                            :key="loc.id"
                                            @mousedown.prevent="selectFavoriteLocation(loc.name)"
                                            style="padding: 8px 12px; cursor: pointer; font-size: 14px;"
                                            onmouseover="this.style.background='#f5f5f5'"
                                            onmouseout="this.style.background='#fff'"
                                        >{{ loc.name }}</div>
                                    </div>
                                </div>
                                <p v-if="!favoriteLocations.length" class="text-muted" style="font-size: 12px; margin-top: 4px;">
                                    可在「代理与位置」页设置常用位置，之后这里会出现下拉候选
                                </p>
                            </div>
                        </div>
                    </div>
                    <button class="btn btn-success btn-block" @click="createBatchUpload" :disabled="!batchForm.account_id || batchForm.videoFiles.length === 0">
                        批量上传
                    </button>
                </div>
            </div>

            <!-- 任务列表 -->
            <div v-if="tab === 'tasks'">
                <div class="card">
                    <div class="flex-between" style="margin-bottom: 16px;">
                        <div class="card-title" style="margin-bottom: 0;">上传任务</div>
                        <div class="action-group">
                            <span v-if="selectedTaskIds.length" style="color: #666; font-size: 13px;">
                                已选 {{ selectedTaskIds.length }} 项
                            </span>
                            <button
                                class="btn btn-danger btn-small"
                                :disabled="!selectedTaskIds.length"
                                @click="deleteSelectedTasks()"
                            >删除选中</button>
                            <button class="btn btn-secondary btn-small" @click="loadTasks()">刷新</button>
                        </div>
                    </div>
                    <!-- 整表横向滚动：视频名/描述/位置内容可能很长，让它们保持原宽并允许左右滑动 -->
                    <div v-if="tasks.length" style="overflow-x: auto; -webkit-overflow-scrolling: touch;">
                        <table class="table" style="min-width: 1180px;">
                            <thead>
                                <tr>
                                    <th style="width: 36px;">
                                        <input
                                            type="checkbox"
                                            :checked="isAllSelectableSelected"
                                            :indeterminate.prop="isPartiallySelected"
                                            :disabled="!selectableTaskIds.length"
                                            @change="toggleSelectAllTasks($event.target.checked)"
                                            title="全选当前列表中可删除的任务"
                                        />
                                    </th>
                                    <th style="width: 56px;">序号</th>
                                    <th style="width: 110px;">账号</th>
                                    <th style="min-width: 220px;">视频</th>
                                    <th style="min-width: 240px;">描述</th>
                                    <th style="min-width: 140px;">位置</th>
                                    <th style="width: 92px;">状态</th>
                                    <th style="width: 160px;">创建时间</th>
                                    <th style="width: 140px;">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(task, idx) in tasks" :key="task.id">
                                    <td>
                                        <input
                                            type="checkbox"
                                            :value="task.id"
                                            v-model="selectedTaskIds"
                                            :disabled="isTaskActive(task.status)"
                                            :title="isTaskActive(task.status) ? '正在执行中，无法删除' : ''"
                                        />
                                    </td>
                                    <td :title="'内部 ID #' + task.id">{{ idx + 1 }}</td>
                                    <td>{{ getAccountName(task.account_id) }}</td>
                                    <td :title="task.video_path">{{ getFileName(task.video_path) }}</td>
                                    <td :title="task.description || task.title || '-'">{{ task.description || task.title || '-' }}</td>
                                    <td :title="task.location_label || '-'">{{ task.location_label || '-' }}</td>
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
                    </div>
                    <div v-else class="empty-state">暂无上传任务</div>
                </div>
            </div>

            <div v-if="tab === 'proxies'">
                <div class="card">
                    <div class="flex-between" style="margin-bottom: 16px;">
                        <div class="card-title" style="margin-bottom: 0;">代理与位置</div>
                        <div class="action-group">
                            <button class="btn btn-secondary btn-small" @click="checkAllProxyProfiles" :disabled="checkingAllProxies">批量检测</button>
                            <button class="btn btn-primary btn-small" @click="openProxyModal()">+ 添加代理</button>
                        </div>
                    </div>
                    <table class="table" v-if="proxyProfiles.length">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>名称</th>
                                <th>协议</th>
                                <th>地址</th>
                                <th>状态</th>
                                <th>出口 IP</th>
                                <th>位置</th>
                                <th>运营商</th>
                                <th>最近检测</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="p in proxyProfiles" :key="p.id">
                                <td>{{ p.id }}</td>
                                <td>{{ p.name }}</td>
                                <td>{{ String(p.scheme || '').toUpperCase() }}</td>
                                <td>{{ p.host }}:{{ p.port }}</td>
                                <td><span :class="['badge', p.enabled ? 'badge-success' : 'badge-default']">{{ p.enabled ? '启用' : '停用' }}</span></td>
                                <td>{{ p.last_ip || '-' }}</td>
                                <td>{{ [p.last_country, p.last_region, p.last_city].filter(Boolean).join(' ') || '-' }}</td>
                                <td class="truncate" :title="p.last_check_error || p.last_isp || '-'">{{ p.last_check_error || p.last_isp || '-' }}</td>
                                <td>{{ formatDate(p.last_checked_at) }}</td>
                                <td>
                                    <div class="action-group">
                                        <button class="btn btn-secondary btn-small" @click="checkProxyProfile(p.id)">检测</button>
                                        <button class="btn btn-primary btn-small" @click="openProxyModal(p)">编辑</button>
                                        <button class="btn btn-danger btn-small" @click="deleteProxyProfile(p.id)">删除</button>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    <div v-else class="empty-state">暂无代理 Profile</div>
                </div>

                <!-- 常用发表位置 —— 用户在批量上传"发表位置"输入框里可直接下拉选择 -->
                <div class="card">
                    <div class="flex-between" style="margin-bottom: 16px;">
                        <div class="card-title" style="margin-bottom: 0;">常用发表位置</div>
                    </div>
                    <div class="form-group" style="display: flex; gap: 8px;">
                        <input
                            v-model.trim="newFavoriteLocation"
                            type="text"
                            placeholder="例如：深圳人民公园、上海陆家嘴、北京三里屯"
                            @keyup.enter="addFavoriteLocation"
                            style="flex: 1;"
                        />
                        <button class="btn btn-primary btn-small" @click="addFavoriteLocation" :disabled="!newFavoriteLocation">+ 添加</button>
                    </div>
                    <table class="table" v-if="favoriteLocations.length">
                        <thead>
                            <tr>
                                <th style="width: 56px;">序号</th>
                                <th>位置名称</th>
                                <th style="width: 160px;">创建时间</th>
                                <th style="width: 100px;">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(loc, idx) in favoriteLocations" :key="loc.id">
                                <td>{{ idx + 1 }}</td>
                                <td>{{ loc.name }}</td>
                                <td>{{ formatDate(loc.created_at) }}</td>
                                <td>
                                    <button class="btn btn-danger btn-small" @click="deleteFavoriteLocation(loc.id)">删除</button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    <div v-else class="empty-state">暂无常用位置；添加后可在批量上传页的「发表位置」下拉选择</div>
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

            <!-- 添加账号弹窗（已改为点击「＋ 添加」直接创建并登录，保留占位避免破坏模板结构） -->
            <div v-if="false" class="modal-overlay">
                <div class="modal-box">
                    <h3>添加视频号账号</h3>
                </div>
            </div>

            <div v-if="showProxyModal" class="modal-overlay" @click.self="closeProxyModal">
                <div class="modal-box">
                    <h3>{{ proxyForm.id ? '编辑代理 Profile' : '添加代理 Profile' }}</h3>
                    <div class="form-group">
                        <label>名称</label>
                        <input v-model.trim="proxyForm.name" type="text" placeholder="例如：深圳 01">
                    </div>
                    <div class="row">
                        <div class="col">
                            <div class="form-group">
                                <label>协议</label>
                                <select v-model="proxyForm.scheme">
                                    <option value="http">HTTP</option>
                                    <option value="socks5">Socks5</option>
                                </select>
                            </div>
                        </div>
                        <div class="col">
                            <div class="form-group">
                                <label>主机</label>
                                <input v-model.trim="proxyForm.host" type="text" placeholder="127.0.0.1">
                            </div>
                        </div>
                        <div class="col">
                            <div class="form-group">
                                <label>端口</label>
                                <input v-model.number="proxyForm.port" type="number" min="1" max="65535">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" v-model="proxyForm.enabled">
                            启用
                        </label>
                    </div>
                    <div class="modal-actions">
                        <button class="btn btn-secondary" @click="closeProxyModal">取消</button>
                        <button class="btn btn-primary" @click="saveProxyProfile" :disabled="!proxyForm.name || !proxyForm.host || !proxyForm.port">保存</button>
                    </div>
                </div>
            </div>

            <div v-if="accountDeleteModal.show" class="modal-overlay" @click.self="closeAccountDeleteModal">
                <div class="modal-box">
                    <h3>删除视频号账号</h3>
                    <p style="margin: 0 0 20px; color: #4b5563; line-height: 1.6;">{{ accountDeleteModalMessage }}</p>
                    <div class="modal-actions">
                        <button class="btn btn-secondary" @click="closeAccountDeleteModal" :disabled="accountDeleteModal.busy">取消</button>
                        <button class="btn btn-danger" @click="confirmAccountDelete" :disabled="accountDeleteModal.busy">
                            {{ accountDeleteModal.busy ? '删除中...' : '确定删除' }}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `,

    setup(props) {
        // 任务的「进行中」状态：上传 / 处理 / 填写 / 发布。
        // 这些状态的任务不允许批量删除，否则会让仍在跑的浏览器自动化任务变成孤儿任务。
        const ACTIVE_TASK_STATUSES = ['uploading', 'processing', 'filling', 'publishing'];

        const tab = ref(props.initialTab || 'accounts');
        const accounts = ref([]);
        const tasks = ref([]);
        const selectedTaskIds = ref([]);
        const selectedAccount = ref(null);
        const selectedAccountIds = ref([]);
        const accountDetailTab = ref('upload');
        const trafficFilter = reactive({
            grace_period_hours: 48,
            min_views: 1000,
        });
        const trafficCandidates = ref([]);
        const selectedTrafficIds = ref([]);
        const trafficScanning = ref(false);
        const trafficDeleting = ref(false);
        const trafficScannedOnce = ref(false);
        const trafficScanMeta = reactive({ scanned: null });
        let trafficScanPollTimer = null;
        const schedules = ref([]);
        const proxyProfiles = ref([]);
        const favoriteLocations = ref([]);
        const newFavoriteLocation = ref('');
        // 发表位置自定义 combobox：是否展开下拉浮层
        const showLocationDropdown = ref(false);
        // 给 combobox 容器拿一个 ref，点击外部时用来判定是否要关闭浮层
        const locationComboboxRef = ref(null);
        // 上传代理同款 combobox 的状态
        const showProxyDropdown = ref(false);
        const proxyComboboxRef = ref(null);
        const showAddAccount = ref(false);
        const showProxyModal = ref(false);
        const accountDeleteModal = reactive({
            show: false,
            mode: 'single',
            ids: [],
            names: [],
            busy: false,
        });
        const newAccountName = ref('');
        const addingAccount = ref(false);
        const refreshingIds = ref(new Set());
        const isBrowsingBatchFiles = ref(false);
        const checkingAllProxies = ref(false);
        const browserCanvasRef = ref(null);
        const browserHostRef = ref(null);
        const nativeBrowserVisible = ref(false);
        // 原生 WebView2 是 WinForms 控件，会盖住 HTML 弹窗；弹窗期间需先藏起再恢复
        const nativeBrowserHiddenForModal = ref(false);
        const hasNativeBrowser = computed(() => Boolean(getDesktopApi()?.showWeixinBrowser));
        const loginModal = reactive({
            show: false,
            sessionId: '',
            accountId: null,
            status: '',
            message: '',
            qr: '',
            url: ''
        });
        let loginPollTimer = null;
        let browserWheelTimer = null;
        let browserActiveNotified = false;
        let nativeBrowserResizeObserver = null;
        let nativeStatusTimer = null;
        const message = reactive({ show: false, type: 'info', text: '' });
        const proxyForm = reactive({
            id: null,
            name: '',
            scheme: 'http',
            host: '127.0.0.1',
            port: 0,
            enabled: true
        });

        // 启动时的全量账号刷新状态。Polling 后端 /accounts/refresh-status 得到。
        // is_refreshing=true 期间：账号管理页所有按钮 disable，避免与浏览器自动化冲突。
        const refreshAllState = reactive({
            is_refreshing: false,
            started_at: null,
            finished_at: null,
            last_stats: null,
            last_error: null,
        });
        let refreshPollTimer = null;

        const DEFAULT_BATCH_DESCRIPTION = '#ys点击上方❤【免费剧集】0元看全集';
        const DEFAULT_LOCATION_LABEL = '樱桃沟管委会西胡垌社区综合性文化服务中心';
        const batchForm = reactive({
            account_id: '',
            videoFiles: [],
            descriptionStr: DEFAULT_BATCH_DESCRIPTION,
            drama_link: '',
            proxy_profile_id: '',
            location_label: DEFAULT_LOCATION_LABEL
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

        async function openWeixinPostList(accountId) {
            try {
                const res = await props.api.openWeixinPostList(accountId);
                showMessage(res.message || '正在打开浏览器…', 'info');
            } catch (e) {
                const msg = typeof e === 'object' && e?.detail ? e.detail : (e.message || String(e));
                showMessage('打开失败: ' + msg, 'error');
            }
        }

        function getAccountName(id) {
            const a = accounts.value.find(a => a.id === id);
            return a ? a.name : '#' + id;
        }

        async function syncTrafficScanState(accountId) {
            if (!accountId) return;
            try {
                const res = await props.api.getWeixinTrafficScanStatus(accountId);
                if (res.is_scanning) {
                    trafficScanning.value = true;
                    startTrafficScanPoll(accountId);
                    return;
                }
                trafficScanning.value = false;
                if (res.status === 'success' || (res.candidates && res.candidates.length)) {
                    trafficScannedOnce.value = true;
                    trafficScanMeta.scanned = res.scanned ?? null;
                    trafficCandidates.value = res.candidates || [];
                }
            } catch (_) {
                // 同步失败不打断账号切换
            }
        }

        function selectAccount(acc) {
            hideNativeWeixinBrowser();
            const prevId = selectedAccount.value?.id;
            selectedAccount.value = acc;
            accountDetailTab.value = 'upload';
            batchForm.account_id = acc.id;
            // 同一账号重选：保留候选与轮询，避免后台扫描被 UI 掐断
            if (prevId != null && Number(prevId) === Number(acc.id)) {
                return;
            }
            selectedTrafficIds.value = [];
            trafficCandidates.value = [];
            trafficScannedOnce.value = false;
            trafficScanMeta.scanned = null;
            stopTrafficScanPoll();
            trafficScanning.value = false;
            // 换账号后若该账号后台仍在扫 / 已有结果，立刻接上
            syncTrafficScanState(acc.id);
        }

        const selectedAccountTasks = computed(() => {
            if (!selectedAccount.value) return [];
            return tasks.value.filter(t => Number(t.account_id) === Number(selectedAccount.value.id));
        });

        function goAccountUpload(acc) {
            batchForm.account_id = acc.id;
            accountDetailTab.value = 'upload';
            showMessage(`已选择账号：${acc.name}`, 'success');
        }

        const enabledProxyProfiles = computed(() => proxyProfiles.value.filter(p => p.enabled));

        function proxyProfileOptionLabel(p) {
            const city = p.last_city || p.last_region || p.last_country || '未检测';
            return `${p.name} - ${city}`;
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
                const alive = new Set(accounts.value.map(a => Number(a.id)));
                selectedAccountIds.value = selectedAccountIds.value.filter(id => alive.has(Number(id)));
                if (selectedAccount.value) {
                    selectedAccount.value = accounts.value.find(a => a.id === selectedAccount.value.id) || null;
                }
            } catch (e) {
                console.error(e);
            }
        }

        async function loadTasks() {
            try {
                const res = await props.api.getWeixinTasks();
                tasks.value = res.tasks || [];
                // 列表更新后，把已选 ID 收敛到当前列表里仍存在且仍可删的任务
                const allowed = new Set(
                    tasks.value
                        .filter(t => !isTaskActive(t.status))
                        .map(t => t.id)
                );
                selectedTaskIds.value = selectedTaskIds.value.filter(id => allowed.has(id));
            } catch (e) {
                console.error(e);
            }
        }

        function isTaskActive(status) {
            return ACTIVE_TASK_STATUSES.includes(status);
        }

        const selectableTaskIds = computed(() =>
            selectedAccountTasks.value.filter(t => !isTaskActive(t.status)).map(t => t.id)
        );
        const isAllSelectableSelected = computed(() =>
            selectableTaskIds.value.length > 0 &&
            selectableTaskIds.value.every(id => selectedTaskIds.value.includes(id))
        );
        const isPartiallySelected = computed(() =>
            selectedTaskIds.value.length > 0 && !isAllSelectableSelected.value
        );

        function toggleSelectAllTasks(checked) {
            selectedTaskIds.value = checked ? [...selectableTaskIds.value] : [];
        }

        async function deleteSelectedTasks() {
            const ids = [...selectedTaskIds.value];
            if (!ids.length) return;
            const ok = await appConfirm({
                title: '批量删除任务',
                message: `确定删除已选中的 ${ids.length} 个任务？`,
                confirmText: '确定删除',
            });
            if (!ok) return;
            try {
                const res = await props.api.batchDeleteWeixinTasks(ids);
                selectedTaskIds.value = [];
                await loadTasks();
                showMessage(res.message || '批量删除完成', 'success');
            } catch (e) {
                showMessage('批量删除失败: ' + (e.detail || e.message || e), 'error');
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

        async function loadProxyProfiles() {
            try {
                const res = await props.api.getWeixinProxyProfiles();
                proxyProfiles.value = res.profiles || [];
            } catch (e) {
                showMessage('加载代理 Profile 失败: ' + (e.detail || e.message || e), 'error');
            }
        }

        async function loadFavoriteLocations() {
            try {
                const res = await props.api.listWeixinFavoriteLocations();
                favoriteLocations.value = res.locations || [];
            } catch (e) {
                showMessage('加载常用位置失败: ' + (e.detail || e.message || e), 'error');
            }
        }

        async function addFavoriteLocation() {
            const name = (newFavoriteLocation.value || '').trim();
            if (!name) return;
            try {
                await props.api.createWeixinFavoriteLocation(name);
                newFavoriteLocation.value = '';
                await loadFavoriteLocations();
                showMessage('已添加常用位置', 'success');
            } catch (e) {
                showMessage('添加失败: ' + (e.detail || e.message || e), 'error');
            }
        }

        async function deleteFavoriteLocation(id) {
            const ok = await appConfirm({
                title: '删除常用位置',
                message: '确定删除该常用位置？',
                confirmText: '确定删除',
            });
            if (!ok) return;
            try {
                await props.api.deleteWeixinFavoriteLocation(id);
                await loadFavoriteLocations();
                showMessage('已删除', 'success');
            } catch (e) {
                showMessage('删除失败: ' + (e.detail || e.message || e), 'error');
            }
        }

        // 用户输入文字时，下拉里只显示包含该文字的候选；没输入时全部显示
        const filteredFavoriteLocations = computed(() => {
            const q = (batchForm.location_label || '').trim().toLowerCase();
            if (!q) return favoriteLocations.value;
            return favoriteLocations.value.filter(l => (l.name || '').toLowerCase().includes(q));
        });

        function selectFavoriteLocation(name) {
            batchForm.location_label = name;
            showLocationDropdown.value = false;
        }

        // 上传代理 combobox 当前选中项的展示文案
        const selectedProxyDisplay = computed(() => {
            const id = batchForm.proxy_profile_id;
            if (!id && id !== 0) return '不指定代理 Profile';
            const p = enabledProxyProfiles.value.find(x => x.id === parseInt(id));
            return p ? proxyProfileOptionLabel(p) : '不指定代理 Profile';
        });

        function selectProxyProfile(id) {
            batchForm.proxy_profile_id = id;
            showProxyDropdown.value = false;
        }

        // 点击 combobox 外部时关闭下拉浮层（mousedown 比 click 更稳，可避开按钮自身 click）
        function handleClickOutsideComboboxes(event) {
            const locRoot = locationComboboxRef.value;
            if (locRoot && !locRoot.contains(event.target)) {
                showLocationDropdown.value = false;
            }
            const proxyRoot = proxyComboboxRef.value;
            if (proxyRoot && !proxyRoot.contains(event.target)) {
                showProxyDropdown.value = false;
            }
        }

        function openProxyModal(profile = null) {
            if (profile) {
                proxyForm.id = profile.id;
                proxyForm.name = profile.name || '';
                proxyForm.scheme = profile.scheme || 'http';
                proxyForm.host = profile.host || '127.0.0.1';
                proxyForm.port = profile.port || 0;
                proxyForm.enabled = !!profile.enabled;
            } else {
                proxyForm.id = null;
                proxyForm.name = '';
                proxyForm.scheme = 'http';
                proxyForm.host = '127.0.0.1';
                proxyForm.port = 0;
                proxyForm.enabled = true;
            }
            showProxyModal.value = true;
        }

        function closeProxyModal() {
            showProxyModal.value = false;
        }

        async function saveProxyProfile() {
            const payload = {
                name: proxyForm.name,
                scheme: proxyForm.scheme,
                host: proxyForm.host,
                port: Number(proxyForm.port),
                enabled: !!proxyForm.enabled
            };
            try {
                if (proxyForm.id) {
                    await props.api.updateWeixinProxyProfile(proxyForm.id, payload);
                } else {
                    await props.api.createWeixinProxyProfile(payload);
                }
                closeProxyModal();
                await loadProxyProfiles();
                showMessage('代理 Profile 已保存', 'success');
            } catch (e) {
                showMessage('保存代理失败: ' + (e.detail || e.message || e), 'error');
            }
        }

        async function deleteProxyProfile(id) {
            const ok = await appConfirm({
                title: '删除代理 Profile',
                message: '确定删除该代理 Profile？',
                confirmText: '确定删除',
            });
            if (!ok) return;
            try {
                await props.api.deleteWeixinProxyProfile(id);
                await loadProxyProfiles();
                showMessage('代理 Profile 已删除', 'success');
            } catch (e) {
                showMessage('删除代理失败: ' + (e.detail || e.message || e), 'error');
            }
        }

        async function checkProxyProfile(id) {
            try {
                const res = await props.api.checkWeixinProxyProfile(id);
                await loadProxyProfiles();
                showMessage(res.status === 'success' ? '代理检测成功' : ('代理检测失败: ' + (res.message || '不可用')), res.status === 'success' ? 'success' : 'error');
            } catch (e) {
                showMessage('代理检测失败: ' + (e.detail || e.message || e), 'error');
            }
        }

        async function checkAllProxyProfiles() {
            checkingAllProxies.value = true;
            try {
                await props.api.checkAllWeixinProxyProfiles();
                await loadProxyProfiles();
                showMessage('批量检测完成', 'success');
            } catch (e) {
                showMessage('批量检测失败: ' + (e.detail || e.message || e), 'error');
            } finally {
                checkingAllProxies.value = false;
            }
        }

        async function addAccount() {
            if (addingAccount.value || refreshAllState.is_refreshing) return;
            addingAccount.value = true;
            try {
                const created = await props.api.createWeixinAccount();
                await loadAccounts();
                const account = created.account || accounts.value.find(a => a.id === created.account?.id) || accounts.value[0];
                if (account) {
                    selectAccount(account);
                    accountDetailTab.value = 'manage';
                    if (hasNativeBrowser.value) {
                        await startNativeWeixinBrowser(true);
                        showMessage('账号已创建，请扫码登录', 'success');
                    } else {
                        await loginAccount(account.id);
                        showMessage('账号已创建，请扫码登录', 'success');
                    }
                } else {
                    showMessage('账号已创建', 'success');
                }
            } catch (e) {
                showMessage('创建失败: ' + (e.message || e), 'error');
            } finally {
                addingAccount.value = false;
            }
        }

        async function loginAccount(id) {
            try {
                const res = await props.api.loginWeixinAccountEmbedded(id);
                loginModal.show = true;
                loginModal.sessionId = res.session_id;
                loginModal.accountId = id;
                loginModal.status = 'starting';
                loginModal.message = res.message || '正在加载视频号页面';
                loginModal.qr = '';
                loginModal.url = '';
                browserActiveNotified = false;
                accountDetailTab.value = 'manage';
                if (loginPollTimer) clearInterval(loginPollTimer);
                await pollEmbeddedLogin();
                loginPollTimer = setInterval(pollEmbeddedLogin, 1000);
            } catch (e) {
                showMessage('登录失败: ' + getErrorMessage(e), 'error');
            }
        }

        async function openAccountManagement() {
            accountDetailTab.value = 'manage';
            if (!selectedAccount.value) return;
            if (selectedAccount.value.status === 'active') {
                await startNativeWeixinBrowser(false);
            }
        }

        function nativeBrowserBounds() {
            const host = browserHostRef.value;
            if (!host) return null;
            const rect = host.getBoundingClientRect();
            return {
                left: rect.left,
                top: rect.top,
                width: rect.width,
                height: rect.height
            };
        }

        async function syncNativeBrowserBounds() {
            const desktop = getDesktopApi();
            const bounds = nativeBrowserBounds();
            if (!desktop?.updateWeixinBrowserBounds || !bounds || !nativeBrowserVisible.value) return;
            await desktop.updateWeixinBrowserBounds(bounds);
        }

        async function startNativeWeixinBrowser(forceLogin = false) {
            if (!selectedAccount.value) return;
            nativeBrowserVisible.value = true;
            await nextTick();
            const desktop = getDesktopApi();
            if (!desktop?.showWeixinBrowser) return;
            const result = await desktop.showWeixinBrowser({
                account_id: selectedAccount.value.id,
                status: forceLogin ? 'expired' : selectedAccount.value.status,
                cookie_path: selectedAccount.value.cookie_path,
                bounds: nativeBrowserBounds()
            });
            if (result?.status === 'error') {
                nativeBrowserVisible.value = false;
                showMessage('视频号页面加载失败：' + getErrorMessage(result), 'error');
                return;
            }
            if (!nativeBrowserResizeObserver && browserHostRef.value) {
                nativeBrowserResizeObserver = new ResizeObserver(syncNativeBrowserBounds);
                nativeBrowserResizeObserver.observe(browserHostRef.value);
            }
            if (!nativeStatusTimer) {
                nativeStatusTimer = setInterval(async () => {
                    await loadAccounts();
                    if (selectedAccount.value) {
                        selectedAccount.value = accounts.value.find(a => a.id === selectedAccount.value.id) || selectedAccount.value;
                    }
                }, 3000);
            }
        }

        async function hideNativeWeixinBrowser() {
            nativeBrowserVisible.value = false;
            const desktop = getDesktopApi();
            if (desktop?.hideWeixinBrowser) await desktop.hideWeixinBrowser();
        }

        async function suspendNativeBrowserForModal() {
            if (!nativeBrowserVisible.value) return;
            nativeBrowserHiddenForModal.value = true;
            await hideNativeWeixinBrowser();
        }

        async function resumeNativeBrowserAfterModal() {
            if (!nativeBrowserHiddenForModal.value) return;
            nativeBrowserHiddenForModal.value = false;
            if (
                tab.value === 'accounts'
                && accountDetailTab.value === 'manage'
                && selectedAccount.value
            ) {
                await startNativeWeixinBrowser(selectedAccount.value.status !== 'active');
            }
        }

        async function reloadNativeWeixinBrowser() {
            const desktop = getDesktopApi();
            if (!nativeBrowserVisible.value) {
                await startNativeWeixinBrowser(selectedAccount.value?.status !== 'active');
            } else if (desktop?.reloadWeixinBrowser) {
                await desktop.reloadWeixinBrowser();
            }
        }

        async function backNativeWeixinBrowser() {
            const desktop = getDesktopApi();
            if (desktop?.backWeixinBrowser) await desktop.backWeixinBrowser();
        }

        async function restartAccountBrowser() {
            if (!selectedAccount.value) return;
            if (loginModal.sessionId) {
                await cancelEmbeddedLogin(false);
            }
            await loginAccount(selectedAccount.value.id);
        }

        async function pollEmbeddedLogin() {
            if (!loginModal.sessionId) return;
            try {
                const res = await props.api.getWeixinLoginSession(loginModal.sessionId);
                const session = res.session || {};
                loginModal.status = session.status || '';
                loginModal.message = session.message || '';
                loginModal.qr = session.qr || loginModal.qr;
                loginModal.url = session.url || loginModal.url;
                if (loginModal.status === 'active' && !browserActiveNotified) {
                    browserActiveNotified = true;
                    await loadAccounts();
                    if (selectedAccount.value) {
                        selectedAccount.value = accounts.value.find(a => a.id === selectedAccount.value.id) || selectedAccount.value;
                    }
                    showMessage('视频号后台已加载', 'success');
                }
                if (['failed', 'error', 'timeout', 'cancelled'].includes(loginModal.status)) {
                    if (loginPollTimer) {
                        clearInterval(loginPollTimer);
                        loginPollTimer = null;
                    }
                    await loadAccounts();
                    if (selectedAccount.value) {
                        selectedAccount.value = accounts.value.find(a => a.id === selectedAccount.value.id) || selectedAccount.value;
                    }
                    showMessage('页面已停止：' + (loginModal.message || loginModal.status), 'info');
                }
            } catch (e) {
                if (loginPollTimer) clearInterval(loginPollTimer);
                loginPollTimer = null;
                showMessage('登录状态获取失败: ' + getErrorMessage(e), 'error');
            }
        }

        async function cancelEmbeddedLogin(reloadAccounts = true) {
            const sessionId = loginModal.sessionId;
            if (loginPollTimer) {
                clearInterval(loginPollTimer);
                loginPollTimer = null;
            }
            loginModal.show = false;
            loginModal.sessionId = '';
            loginModal.qr = '';
            loginModal.url = '';
            if (sessionId) {
                try {
                    await props.api.cancelWeixinLoginSession(sessionId);
                } catch (e) {
                    console.warn(e);
                }
            }
            if (reloadAccounts) await loadAccounts();
        }

        async function sendBrowserInput(payload) {
            if (!loginModal.sessionId) return;
            try {
                await props.api.sendWeixinBrowserInput(loginModal.sessionId, payload);
            } catch (e) {
                console.warn('视频号页面操作失败:', getErrorMessage(e));
            }
        }

        function browserPointerRatios(event) {
            const rect = event.currentTarget.getBoundingClientRect();
            return {
                x_ratio: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
                y_ratio: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))
            };
        }

        function handleBrowserClick(event) {
            browserCanvasRef.value?.focus();
            sendBrowserInput({ type: 'click', ...browserPointerRatios(event) });
        }

        function handleBrowserWheel(event) {
            if (!loginModal.sessionId || browserWheelTimer) return;
            const ratios = browserPointerRatios(event);
            sendBrowserInput({
                type: 'wheel',
                ...ratios,
                delta_x: event.deltaX,
                delta_y: event.deltaY
            });
            browserWheelTimer = setTimeout(() => { browserWheelTimer = null; }, 80);
        }

        function handleBrowserKeydown(event) {
            if (!loginModal.sessionId || ['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(event.key)) return;
            sendBrowserInput({ type: 'key', key: event.key, code: event.code || event.key });
        }

        function sendBrowserNavigation(type) {
            sendBrowserInput({ type });
        }

        async function refreshAccount(id) {
            refreshingIds.value.add(id);
            try {
                const res = await props.api.refreshWeixinAccount(id);
                await loadAccounts();
                showMessage(res.message, res.status === 'success' ? 'success' : 'info');
            } catch (e) {
                showMessage('刷新失败: ' + (e.message || e), 'error');
            } finally {
                refreshingIds.value.delete(id);
            }
        }

        const isAllAccountsSelected = computed(() => {
            return accounts.value.length > 0
                && selectedAccountIds.value.length === accounts.value.length;
        });

        const isPartiallyAccountsSelected = computed(() => {
            return selectedAccountIds.value.length > 0 && !isAllAccountsSelected.value;
        });

        const accountDeleteModalMessage = computed(() => {
            if (accountDeleteModal.mode === 'single') {
                const name = accountDeleteModal.names[0] || '未命名账号';
                return `确定删除视频号账号「${name}」？删除后需重新扫码登录，相关上传任务与定时计划也会一并清除。`;
            }
            const n = accountDeleteModal.ids.length;
            return `确定删除选中的 ${n} 个视频号账号？删除后需重新扫码登录，相关上传任务与定时计划也会一并清除。`;
        });

        function toggleAccountSelect(id, checked) {
            const numId = Number(id);
            const set = new Set(selectedAccountIds.value.map(Number));
            if (checked) set.add(numId);
            else set.delete(numId);
            selectedAccountIds.value = Array.from(set);
        }

        function toggleSelectAllAccounts() {
            if (isAllAccountsSelected.value) {
                selectedAccountIds.value = [];
            } else {
                selectedAccountIds.value = accounts.value.map(a => Number(a.id));
            }
        }

        async function openDeleteAccount(acc) {
            if (!acc) return;
            await suspendNativeBrowserForModal();
            accountDeleteModal.show = true;
            accountDeleteModal.mode = 'single';
            accountDeleteModal.ids = [Number(acc.id)];
            accountDeleteModal.names = [acc.name || '未命名账号'];
            accountDeleteModal.busy = false;
        }

        async function openBatchDeleteAccounts() {
            if (!selectedAccountIds.value.length) return;
            const ids = selectedAccountIds.value.map(Number);
            const names = ids.map(id => {
                const acc = accounts.value.find(a => Number(a.id) === id);
                return acc ? acc.name : `#${id}`;
            });
            await suspendNativeBrowserForModal();
            accountDeleteModal.show = true;
            accountDeleteModal.mode = 'batch';
            accountDeleteModal.ids = ids;
            accountDeleteModal.names = names;
            accountDeleteModal.busy = false;
        }

        async function closeAccountDeleteModal() {
            if (accountDeleteModal.busy) return;
            accountDeleteModal.show = false;
            accountDeleteModal.ids = [];
            accountDeleteModal.names = [];
            await resumeNativeBrowserAfterModal();
        }

        async function applyDeletedAccounts(deletedIds) {
            const deleted = new Set((deletedIds || []).map(Number));
            selectedAccountIds.value = selectedAccountIds.value.filter(id => !deleted.has(Number(id)));
            if (selectedAccount.value && deleted.has(Number(selectedAccount.value.id))) {
                await hideNativeWeixinBrowser();
                selectedAccount.value = null;
                accountDetailTab.value = 'upload';
                batchForm.account_id = '';
            }
        }

        async function confirmAccountDelete() {
            const ids = accountDeleteModal.ids.map(Number);
            if (!ids.length || accountDeleteModal.busy) return;
            accountDeleteModal.busy = true;
            try {
                if (accountDeleteModal.mode === 'single') {
                    await props.api.deleteWeixinAccount(ids[0]);
                    await applyDeletedAccounts(ids);
                    await loadAccounts();
                    showMessage('账号已删除', 'success');
                } else {
                    const res = await props.api.deleteWeixinAccounts(ids);
                    await applyDeletedAccounts(res.deleted || []);
                    await loadAccounts();
                    const parts = [];
                    if ((res.deleted || []).length) parts.push(`已删除 ${(res.deleted || []).length} 个`);
                    if ((res.skipped_active || []).length) parts.push(`跳过进行中 ${(res.skipped_active || []).length} 个`);
                    if ((res.not_found || []).length) parts.push(`不存在 ${(res.not_found || []).length} 个`);
                    showMessage(parts.join('，') || (res.message || '批量删除完成'), 'success');
                }
                accountDeleteModal.busy = false;
                closeAccountDeleteModal();
            } catch (e) {
                accountDeleteModal.busy = false;
                showMessage('删除失败: ' + getErrorMessage(e), 'error');
            }
        }

        async function browseBatchFiles() {
            if (isBrowsingBatchFiles.value) return;
            isBrowsingBatchFiles.value = true;
            try {
                const res = await props.api.browseFiles();
                if (res.status === 'success' && res.paths) {
                    for (const p of res.paths) {
                        if (!batchForm.videoFiles.includes(p)) {
                            batchForm.videoFiles.push(p);
                        }
                    }
                }
            } catch (e) {
                showMessage('选择文件失败: ' + getErrorMessage(e), 'error');
            } finally {
                isBrowsingBatchFiles.value = false;
            }
        }

        function removeBatchFile(idx) {
            batchForm.videoFiles.splice(idx, 1);
        }

        async function createBatchUpload() {
            try {
                if (!batchForm.videoFiles.length) {
                    showMessage('请选择视频文件', 'error');
                    return;
                }
                const descTrim = (batchForm.descriptionStr || '').trim();
                const descriptions = descTrim
                    ? batchForm.videoFiles.map(() => descTrim)
                    : null;
                const res = await props.api.createWeixinBatchUpload({
                    account_id: parseInt(batchForm.account_id),
                    video_paths: batchForm.videoFiles,
                    descriptions,
                    metadata_source: 'manual',
                    drama_link: batchForm.drama_link || null,
                    proxy_profile_id: batchForm.proxy_profile_id ? parseInt(batchForm.proxy_profile_id) : null,
                    location_label: (batchForm.location_label || '').trim() || null,
                });
                const totalText = typeof res.total === 'number' ? res.total : batchForm.videoFiles.length;
                showMessage(res.message || ('批量任务已创建，共 ' + totalText + ' 个'), 'success');
                batchForm.videoFiles = [];
                batchForm.descriptionStr = DEFAULT_BATCH_DESCRIPTION;
                batchForm.drama_link = '';
                batchForm.location_label = DEFAULT_LOCATION_LABEL;
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
            const ok = await appConfirm({
                title: '删除任务',
                message: '确定删除该任务？',
                confirmText: '确定删除',
            });
            if (!ok) return;
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
            const ok = await appConfirm({
                title: '删除定时计划',
                message: '确定删除该定时计划？',
                confirmText: '确定删除',
            });
            if (!ok) return;
            try {
                await props.api.deleteWeixinSchedule(id);
                await loadSchedules();
                showMessage('定时计划已删除', 'success');
            } catch (e) {
                showMessage('删除失败', 'error');
            }
        }

        function trafficReasonText(reason) {
            return { low_views: '低播放' }[reason] || reason;
        }

        const isAllTrafficSelected = computed(() => {
            const ids = trafficCandidates.value.map(c => c.post_id);
            return ids.length > 0 && ids.every(id => selectedTrafficIds.value.includes(id));
        });

        const isPartiallyTrafficSelected = computed(() => {
            const ids = trafficCandidates.value.map(c => c.post_id);
            const n = ids.filter(id => selectedTrafficIds.value.includes(id)).length;
            return n > 0 && n < ids.length;
        });

        function toggleSelectAllTraffic(checked) {
            selectedTrafficIds.value = checked
                ? trafficCandidates.value.map(c => c.post_id)
                : [];
        }

        function stopTrafficScanPoll() {
            if (trafficScanPollTimer) {
                clearInterval(trafficScanPollTimer);
                trafficScanPollTimer = null;
            }
        }

        function startTrafficScanPoll(accountId) {
            stopTrafficScanPoll();
            let ticks = 0;
            const maxTicks = 900; // 约 30 分钟
            trafficScanPollTimer = setInterval(async () => {
                ticks += 1;
                // 已切到其他账号时不再应用结果，但可继续问状态直到停
                const stillSelected = selectedAccount.value
                    && Number(selectedAccount.value.id) === Number(accountId);
                try {
                    const res = await props.api.getWeixinTrafficScanStatus(accountId);
                    if (res.is_scanning) {
                        if (stillSelected) trafficScanning.value = true;
                        if (ticks < maxTicks) return;
                        stopTrafficScanPoll();
                        if (stillSelected) {
                            trafficScanning.value = false;
                            showMessage('扫描耗时较长，请稍后重新进入流量筛选查看结果', 'warning');
                        }
                        return;
                    }
                    stopTrafficScanPoll();
                    if (!stillSelected) return;
                    trafficScanning.value = false;
                    trafficScannedOnce.value = true;
                    trafficScanMeta.scanned = res.scanned ?? null;
                    trafficCandidates.value = res.candidates || [];
                    selectedTrafficIds.value = [];
                    if (res.status === 'success') {
                        showMessage(`扫描完成：候选 ${trafficCandidates.value.length} 条`, 'success');
                    } else if (res.status === 'idle') {
                        // 无任务
                    } else {
                        showMessage(res.message || '扫描失败', 'error');
                    }
                } catch (e) {
                    if (ticks >= maxTicks) {
                        stopTrafficScanPoll();
                        if (stillSelected) {
                            trafficScanning.value = false;
                            showMessage('扫描状态查询失败: ' + (e.detail || e.message || e), 'error');
                        }
                    }
                }
            }, 2000);
        }

        async function scanTrafficCandidates() {
            if (!selectedAccount.value) return;
            if (selectedAccount.value.status !== 'active') {
                showMessage('请先登录账号后再扫描', 'error');
                return;
            }
            const accountId = selectedAccount.value.id;
            trafficScanning.value = true;
            selectedTrafficIds.value = [];
            try {
                const res = await props.api.scanWeixinTraffic(accountId, {
                    grace_period_hours: Number(trafficFilter.grace_period_hours) || 0,
                    min_views: Number(trafficFilter.min_views) || 0,
                });
                if (res.status === 'error') {
                    trafficScanning.value = false;
                    trafficCandidates.value = [];
                    showMessage(res.message || '扫描失败', 'error');
                    return;
                }
                showMessage(res.message || '扫描已在后台启动', 'info');
                startTrafficScanPoll(accountId);
            } catch (e) {
                trafficScanning.value = false;
                showMessage('扫描失败: ' + (e.detail || e.message || e), 'error');
            }
        }

        async function deleteTrafficPosts(postIds) {
            if (!selectedAccount.value || !postIds?.length) return;
            trafficDeleting.value = true;
            try {
                const res = await props.api.deleteWeixinTrafficPosts(selectedAccount.value.id, postIds);
                const deleted = new Set(res.deleted || []);
                trafficCandidates.value = trafficCandidates.value.filter(c => !deleted.has(c.post_id));
                selectedTrafficIds.value = selectedTrafficIds.value.filter(id => !deleted.has(id));
                if (res.status === 'success' || res.status === 'partial') {
                    showMessage(res.message || '删除完成', deleted.size ? 'success' : 'error');
                } else {
                    showMessage(res.message || '删除失败', 'error');
                }
            } catch (e) {
                showMessage('删除失败: ' + (e.detail || e.message || e), 'error');
            } finally {
                trafficDeleting.value = false;
            }
        }

        async function deleteOneTrafficPost(item) {
            if (!item?.post_id) return;
            const title = item.title || item.post_id;
            const ok = await appConfirm({
                title: '删除平台视频',
                message: `确定删除「${title}」？此操作不可恢复。`,
                confirmText: '确定删除',
            });
            if (!ok) return;
            await deleteTrafficPosts([item.post_id]);
        }

        async function deleteSelectedTrafficPosts() {
            if (!selectedTrafficIds.value.length) return;
            const ok = await appConfirm({
                title: '删除平台视频',
                message: `确定删除选中的 ${selectedTrafficIds.value.length} 条视频？此操作不可恢复。`,
                confirmText: '确定删除',
            });
            if (!ok) return;
            await deleteTrafficPosts([...selectedTrafficIds.value]);
        }

        async function pollRefreshStatus() {
            try {
                const res = await props.api.getWeixinAccountsRefreshStatus();
                const wasRefreshing = refreshAllState.is_refreshing;
                refreshAllState.is_refreshing = !!res.is_refreshing;
                refreshAllState.started_at = res.started_at ?? null;
                refreshAllState.finished_at = res.finished_at ?? null;
                refreshAllState.last_stats = res.last_stats ?? null;
                refreshAllState.last_error = res.last_error ?? null;
                // 刚结束这一次刷新：自动拉取最新账号列表，并停掉 polling
                if (wasRefreshing && !refreshAllState.is_refreshing) {
                    await loadAccounts();
                    stopRefreshPolling();
                    const s = refreshAllState.last_stats;
                    if (s) {
                        showMessage(
                            `账号刷新完成：有效 ${s.valid}，过期 ${s.expired}，异常 ${s.errors}，跳过 ${s.skipped}`,
                            (s.errors > 0 || refreshAllState.last_error) ? 'error' : 'success'
                        );
                    }
                }
            } catch (e) {
                console.error('refresh-status poll failed', e);
            }
        }

        function startRefreshPolling() {
            if (refreshPollTimer) return;
            refreshPollTimer = setInterval(pollRefreshStatus, 1500);
        }
        function stopRefreshPolling() {
            if (refreshPollTimer) {
                clearInterval(refreshPollTimer);
                refreshPollTimer = null;
            }
        }

        async function triggerRefreshAll() {
            try {
                await props.api.refreshAllWeixinAccounts();
                refreshAllState.is_refreshing = true;
                startRefreshPolling();
                showMessage('正在批量刷新账号状态…', 'info');
            } catch (e) {
                showMessage('触发刷新失败: ' + (e.detail || e.message || e), 'error');
            }
        }

        const activateTab = async (nextTab) => {
            if (!nextTab || tab.value === nextTab) return;
            tab.value = nextTab;
            if (nextTab === 'tasks') {
                await loadTasks();
            } else if (nextTab === 'proxies') {
                await Promise.all([loadProxyProfiles(), loadFavoriteLocations()]);
            } else if (nextTab === 'schedule') {
                await loadSchedules();
            }
        };

        watch(() => props.initialTab, (nextTab) => {
            activateTab(nextTab);
        });

        // accounts/proxies 共用 weixin-page：切到代理页不会卸载组件，需主动 hide WebView2
        watch(tab, (nextTab) => {
            if (nextTab !== 'accounts') hideNativeWeixinBrowser();
        });

        watch(accountDetailTab, (nextTab) => {
            if (nextTab !== 'manage') hideNativeWeixinBrowser();
            if (nextTab === 'traffic' && selectedAccount.value) {
                syncTrafficScanState(selectedAccount.value.id);
            }
        });

        onMounted(async () => {
            // 启动时先取一次刷新状态：后端 lifespan 已经在跑一次全量刷新
            await pollRefreshStatus();
            if (refreshAllState.is_refreshing) {
                startRefreshPolling();
                showMessage('正在批量刷新账号状态…', 'info');
            }
            loadAccounts();
            loadSchedules();
            loadProxyProfiles();
            // 批量上传页的位置下拉也依赖常用位置，提前加载一次
            loadFavoriteLocations();
            if (tab.value === 'tasks') {
                loadTasks();
            } else if (tab.value === 'schedule') {
                loadSchedules();
            }
            // 监听全局 mousedown，点 combobox 外部时收起浮层（同时管发表位置 / 上传代理两个）
            document.addEventListener('mousedown', handleClickOutsideComboboxes);
            window.addEventListener('resize', syncNativeBrowserBounds);
            window.addEventListener('scroll', syncNativeBrowserBounds, true);
        });

        onBeforeUnmount(() => {
            stopRefreshPolling();
            stopTrafficScanPoll();
            if (loginPollTimer) {
                clearInterval(loginPollTimer);
                loginPollTimer = null;
            }
            if (browserWheelTimer) clearTimeout(browserWheelTimer);
            if (nativeStatusTimer) clearInterval(nativeStatusTimer);
            if (nativeBrowserResizeObserver) nativeBrowserResizeObserver.disconnect();
            hideNativeWeixinBrowser();
            if (loginModal.sessionId) {
                props.api.cancelWeixinLoginSession(loginModal.sessionId).catch(() => {});
            }
            document.removeEventListener('mousedown', handleClickOutsideComboboxes);
            window.removeEventListener('resize', syncNativeBrowserBounds);
            window.removeEventListener('scroll', syncNativeBrowserBounds, true);
        });

        return {
            tab, accounts, tasks, selectedTaskIds, schedules, proxyProfiles,
            selectedAccount, selectedAccountIds, accountDetailTab, selectedAccountTasks, selectAccount, goAccountUpload,
            trafficFilter, trafficCandidates, selectedTrafficIds, trafficScanning, trafficDeleting,
            trafficScannedOnce, trafficScanMeta, trafficReasonText,
            isAllTrafficSelected, isPartiallyTrafficSelected, toggleSelectAllTraffic,
            scanTrafficCandidates, deleteTrafficPosts, deleteOneTrafficPost, deleteSelectedTrafficPosts,
            favoriteLocations, newFavoriteLocation,
            showLocationDropdown, locationComboboxRef, filteredFavoriteLocations, selectFavoriteLocation,
            showProxyDropdown, proxyComboboxRef, selectedProxyDisplay, selectProxyProfile,
            showAddAccount, showProxyModal, accountDeleteModal, accountDeleteModalMessage, newAccountName, addingAccount, message, refreshingIds, loginModal, browserCanvasRef,
            browserHostRef, nativeBrowserVisible, hasNativeBrowser,
            isBrowsingBatchFiles, checkingAllProxies, refreshAllState,
            proxyForm, enabledProxyProfiles,
            batchForm, scheduleForm,
            formatDate, getFileName, getAccountName, proxyProfileOptionLabel,
            getStatusClass, getStatusText, getTaskStatusClass, getTaskStatusText,
            isTaskActive, selectableTaskIds, isAllSelectableSelected, isPartiallySelected,
            toggleSelectAllTasks, deleteSelectedTasks,
            isAllAccountsSelected, isPartiallyAccountsSelected,
            toggleAccountSelect, toggleSelectAllAccounts,
            openDeleteAccount, openBatchDeleteAccounts, closeAccountDeleteModal, confirmAccountDelete,
            loadAccounts, loadTasks, loadSchedules, loadProxyProfiles, triggerRefreshAll,
            loadFavoriteLocations, addFavoriteLocation, deleteFavoriteLocation,
            addAccount, loginAccount, openAccountManagement, restartAccountBrowser, cancelEmbeddedLogin,
            startNativeWeixinBrowser, reloadNativeWeixinBrowser, backNativeWeixinBrowser,
            handleBrowserClick, handleBrowserWheel, handleBrowserKeydown, sendBrowserNavigation,
            refreshAccount, openWeixinPostList,
            openProxyModal, closeProxyModal, saveProxyProfile, deleteProxyProfile,
            checkProxyProfile, checkAllProxyProfiles,
            browseBatchFiles, removeBatchFile,
            createBatchUpload,
            retryTask, deleteTask,
            createSchedule, deleteSchedule, showMessage
        };
    }
});

// ============================================================================
// 运行日志页面组件
// ============================================================================

app.component('logs-page', {
    props: ['api'],
    template: `
        <div>
            <div class="header">
                <h1>📋 运行日志</h1>
                <p>实时展示应用运行日志，最多保留最新 500 条（进程内缓冲区，重启后清空）</p>
            </div>

            <div class="card">
                <div class="log-toolbar">
                    <select v-model="levelFilter" style="width: auto; min-width: 110px;">
                        <option value="">全部级别</option>
                        <option value="INFO">INFO</option>
                        <option value="WARN">WARN</option>
                        <option value="ERROR">ERROR</option>
                        <option value="DEBUG">DEBUG</option>
                    </select>
                    <label style="display:flex; align-items:center; gap:6px; cursor:pointer; user-select:none;">
                        <input type="checkbox" v-model="autoRefresh" />
                        自动刷新
                    </label>
                    <button class="btn btn-secondary btn-small" @click="fetchLogs" :disabled="loading">
                        {{ loading ? '加载中…' : '🔄 手动刷新' }}
                    </button>
                    <button class="btn btn-secondary btn-small" @click="scrollToBottom" title="滚动到底部">⬇ 最新</button>
                    <button class="btn btn-secondary btn-small" @click="clearView" title="清空当前视图（不影响后端日志）">🗑 清空视图</button>
                    <span style="margin-left:auto; color: var(--text-light); font-size:12px;">
                        共 {{ filteredEntries.length }} 条
                        <span v-if="levelFilter">（已过滤 {{ levelFilter }}）</span>
                    </span>
                </div>

                <div class="log-viewer" ref="viewerRef">
                    <div
                        v-for="entry in filteredEntries"
                        :key="entry.id"
                        class="log-entry"
                    >
                        <span class="log-ts">{{ entry.ts }}</span>
                        <span :class="'log-level log-level-' + entry.level">{{ entry.level }}</span>
                        <span :class="'log-msg log-msg-' + entry.level">{{ entry.msg }}</span>
                    </div>
                    <div v-if="filteredEntries.length === 0" style="color:#6b6050; padding:8px 0;">
                        {{ levelFilter ? '没有匹配 ' + levelFilter + ' 级别的日志' : '暂无日志' }}
                    </div>
                </div>
            </div>
        </div>
    `,

    setup(props) {
        const entries = ref([]);
        const levelFilter = ref('');
        const autoRefresh = ref(true);
        const loading = ref(false);
        const viewerRef = ref(null);
        let maxSeenId = 0;
        let timer = null;
        let userScrolledUp = false;

        const filteredEntries = computed(() => {
            if (!levelFilter.value) return entries.value;
            return entries.value.filter(e => e.level === levelFilter.value);
        });

        const isNearBottom = () => {
            const el = viewerRef.value;
            if (!el) return true;
            return el.scrollHeight - el.scrollTop - el.clientHeight < 60;
        };

        const scrollToBottom = () => {
            const el = viewerRef.value;
            if (el) el.scrollTop = el.scrollHeight;
        };

        const fetchLogs = async () => {
            loading.value = true;
            try {
                const result = await props.api.getLogs(maxSeenId, 200);
                const newEntries = result.entries || [];
                if (newEntries.length > 0) {
                    const shouldScroll = !userScrolledUp && isNearBottom();
                    entries.value = [...entries.value, ...newEntries].slice(-500);
                    maxSeenId = newEntries[newEntries.length - 1].id;
                    if (shouldScroll) {
                        await Vue.nextTick();
                        scrollToBottom();
                    }
                }
            } catch (e) {
                console.error('获取日志失败', e);
            } finally {
                loading.value = false;
            }
        };

        const clearView = () => {
            entries.value = [];
            maxSeenId = 0;
        };

        const startPolling = () => {
            stopPolling();
            timer = setInterval(fetchLogs, 2000);
        };

        const stopPolling = () => {
            if (timer) { clearInterval(timer); timer = null; }
        };

        watch(autoRefresh, (val) => {
            val ? startPolling() : stopPolling();
        });

        onMounted(async () => {
            await fetchLogs();
            scrollToBottom();
            if (autoRefresh.value) startPolling();

            const el = viewerRef.value;
            if (el) {
                el.addEventListener('scroll', () => {
                    userScrolledUp = !isNearBottom();
                });
            }
        });

        onBeforeUnmount(() => {
            stopPolling();
        });

        return {
            entries,
            levelFilter,
            autoRefresh,
            loading,
            viewerRef,
            filteredEntries,
            fetchLogs,
            clearView,
            scrollToBottom
        };
    }
});

// ============================================================================
// 挂载应用
// ============================================================================

app.mount('#app');
