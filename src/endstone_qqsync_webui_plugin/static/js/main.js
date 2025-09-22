// 主JavaScript文件 - QQsync WebUI

class QQSyncUI {
    constructor() {
        this.init();
    }

    init() {
        this.setupTheme();
        this.setupNotifications();
        this.setupEventListeners();
        this.checkServerStatus();
    }

    // 主题切换功能
    setupTheme() {
        const theme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', theme);
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    }

    // 通知系统
    setupNotifications() {
        // 创建通知容器
        if (!document.getElementById('notificationContainer')) {
            const container = document.createElement('div');
            container.id = 'notificationContainer';
            container.style.cssText = `
                position: fixed;
                top: 80px;
                right: 20px;
                z-index: 2000;
                display: flex;
                flex-direction: column;
                gap: 8px;
            `;
            document.body.appendChild(container);
        }
    }

    showNotification(message, type = 'info', duration = 3000) {
        const container = document.getElementById('notificationContainer');
        const notification = document.createElement('div');
        
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <i class="win-icon ${this.getNotificationIcon(type)}"></i>
                <span>${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; color: inherit; cursor: pointer; margin-left: 12px;">
                    <i class="win-icon win-icon-Cancel"></i>
                </button>
            </div>
        `;
        
        container.appendChild(notification);
        
        // 显示动画
        setTimeout(() => notification.classList.add('show'), 100);
        
        // 自动隐藏
        if (duration > 0) {
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, duration);
        }
    }

    getNotificationIcon(type) {
        const icons = {
            success: 'win-icon-CheckMark',
            error: 'win-icon-ErrorBadge',
            warning: 'win-icon-Warning',
            info: 'win-icon-Info'
        };
        return icons[type] || icons.info;
    }

    // 事件监听器设置
    setupEventListeners() {
        // 全局按键监听
        document.addEventListener('keydown', (e) => {
            // Ctrl+R 刷新数据
            if (e.ctrlKey && e.key === 'r') {
                e.preventDefault();
                this.refreshData();
            }
        });

        // API错误处理
        window.addEventListener('unhandledrejection', (e) => {
            console.error('API Error:', e.reason);
            this.showNotification('网络请求失败', 'error');
        });
    }

    // 检查服务器状态
    async checkServerStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            this.updateStatusIndicators(data);
        } catch (error) {
            console.error('Status check failed:', error);
            this.showNotification('无法连接到服务器', 'error');
        }
    }

    updateStatusIndicators(data) {
        // 更新页面上的状态指示器
        const indicators = document.querySelectorAll('[data-status]');
        indicators.forEach(indicator => {
            const statusType = indicator.getAttribute('data-status');
            if (data[statusType] !== undefined) {
                indicator.textContent = data[statusType] ? '正常' : '异常';
                indicator.className = `status-value status-${data[statusType] ? 'success' : 'error'}`;
            }
        });
    }

    // 刷新数据
    async refreshData() {
        this.showNotification('正在刷新数据...', 'info', 1000);
        
        try {
            // 根据当前页面刷新相应数据
            const path = window.location.pathname;
            
            if (path === '/' || path === '/dashboard') {
                await this.refreshDashboard();
            } else if (path === '/config') {
                await this.refreshConfig();
            } else if (path === '/users') {
                await this.refreshUsers();
            } else if (path === '/logs') {
                await this.refreshLogs();
            }
            
            this.showNotification('数据已刷新', 'success');
        } catch (error) {
            this.showNotification('刷新失败', 'error');
        }
    }

    // 仪表板数据刷新
    async refreshDashboard() {
        const response = await fetch('/api/dashboard');
        const data = await response.json();
        
        // 更新统计数据
        this.updateDashboardStats(data.stats);
        
        // 更新最近消息
        if (data.recent_messages) {
            this.updateRecentMessages(data.recent_messages);
        }
    }

    updateDashboardStats(stats) {
        Object.keys(stats).forEach(key => {
            const element = document.getElementById(`stat-${key}`);
            if (element) {
                element.textContent = stats[key];
            }
        });
    }

    updateRecentMessages(messages) {
        const container = document.getElementById('recentMessages');
        if (container) {
            container.innerHTML = messages.map(msg => `
                <div class="message-item">
                    <div class="message-avatar">
                        <img src="/static/img/avatar-default.png" alt="avatar">
                    </div>
                    <div class="message-content">
                        <div class="message-header">
                            <span class="message-sender">${this.escapeHtml(msg.sender)}</span>
                            <span class="message-time">${msg.time}</span>
                        </div>
                        <div class="message-text">${this.escapeHtml(msg.content)}</div>
                    </div>
                </div>
            `).join('');
        }
    }

    // 工具函数
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatTime(timestamp) {
        return new Date(timestamp * 1000).toLocaleString('zh-CN');
    }

    // API调用助手
    async apiCall(endpoint, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            }
        };

        const response = await fetch(endpoint, { ...defaultOptions, ...options });
        
        if (!response.ok) {
            throw new Error(`API call failed: ${response.statusText}`);
        }
        
        return await response.json();
    }

    // 异步操作助手
    async executeWithLoading(asyncFunction, loadingMessage = '处理中...') {
        const loadingNotification = this.showNotification(loadingMessage, 'info', 0);
        
        try {
            const result = await asyncFunction();
            document.querySelector('.notification:last-child')?.remove();
            return result;
        } catch (error) {
            document.querySelector('.notification:last-child')?.remove();
            throw error;
        }
    }
}

// 全局函数
function toggleTheme() {
    window.qqsyncUI.toggleTheme();
}

function showAbout() {
    window.open('https://github.com/yuexps/endstone-qqsync-webui-plugin', '_blank');
}

function showNotification(message, type = 'info', duration = 3000) {
    window.qqsyncUI.showNotification(message, type, duration);
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    window.qqsyncUI = new QQSyncUI();
    
    // 定期检查服务器状态（每30秒）
    setInterval(() => {
        window.qqsyncUI.checkServerStatus();
    }, 30000);
});

// 导出给其他脚本使用
window.QQSyncUI = QQSyncUI;