/**
 * GPU监控 - 调试版本 - 无弹窗版
 * 更新时间: 2025-08-08 - 强制缓存刷新
 */

// 永久禁用所有弹窗 - 不保存原始函数
window.alert = function(message) {
    console.log('[GPU监控] Alert被阻止:', message);
    return undefined;
};

window.confirm = function(message) {
    console.log('[GPU监控] Confirm被阻止:', message);
    return false;
};

window.prompt = function(message, defaultText) {
    console.log('[GPU监控] Prompt被阻止:', message);
    return null;
};

// 同时禁用可能的通知
if ('Notification' in window) {
    window.Notification = function(title, options) {
        console.log('[GPU监控] Notification被阻止:', title, options);
        return {
            close: function() {},
            addEventListener: function() {},
            removeEventListener: function() {}
        };
    };
    window.Notification.permission = 'denied';
    window.Notification.requestPermission = function() {
        console.log('[GPU监控] Notification权限请求被阻止');
        return Promise.resolve('denied');
    };
}
console.log('GPU监控脚本开始加载...');

// 立即创建按钮测试
function createTestButton() {
    console.log('开始创建GPU按钮...');
    
    const button = document.createElement('button');
    button.id = 'gpu-toggle-btn';
    button.innerHTML = 'GPU 状态<br><small style="font-size: 10px; opacity: 0.8;">Ctrl+G 可查看</small>';
    button.style.position = 'fixed';
    button.style.top = '20px';
    button.style.right = '20px';
    button.style.zIndex = '10000';
    button.style.background = '#1769aa';
    button.style.color = 'white';
    button.style.border = 'none';
    button.style.padding = '10px 12px';
    button.style.borderRadius = '8px';
    button.style.cursor = 'pointer';
    button.style.fontSize = '12px';
    button.style.fontWeight = 'bold';
    button.style.boxShadow = '0 4px 12px rgba(0,0,0,0.2)';
    button.style.lineHeight = '1.2';
    button.style.textAlign = 'center';
    
    button.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('GPU按钮被点击');
        toggleGPUMonitor();
    });
    
    document.body.appendChild(button);
    console.log('GPU按钮已创建并添加到页面');
}

// 创建GPU监控窗口
function createGPUMonitorWindow() {
    console.log('开始创建GPU监控窗口...');
    
    // 检查是否已存在
    let existingWindow = document.getElementById('gpu-monitor-window');
    if (existingWindow) {
        console.log('窗口已存在，直接返回');
        return existingWindow;
    }
    
    const container = document.createElement('div');
    container.id = 'gpu-monitor-window';
    container.style.position = 'fixed';
    container.style.top = '70px';
    container.style.right = '20px';
    container.style.width = '320px';
    container.style.background = 'white';
    container.style.borderRadius = '12px';
    container.style.boxShadow = '0 8px 32px rgba(0,0,0,0.2)';
    container.style.zIndex = '9999';
    container.style.display = 'none';
    container.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    container.style.border = '1px solid #e1e8ed';
    
    container.innerHTML = `
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 16px; border-radius: 12px 12px 0 0; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: 600;">GPU 状态</span>
            <button id="gpu-close-btn" style="background: rgba(255,255,255,0.2); border: none; color: white; width: 24px; height: 24px; border-radius: 6px; cursor: pointer; font-size: 16px;">×</button>
        </div>
        <div id="gpu-content" style="padding: 16px; background: #fafbfc; min-height: 120px;">
            <div style="text-align: center; color: #666; padding: 20px;">
                <div style="margin-bottom: 10px;">正在获取GPU信息...</div>
                <div style="font-size: 12px;">请稍候...</div>
            </div>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: #f8f9fa; border-radius: 0 0 12px 12px; border-top: 1px solid #e1e8ed; font-size: 11px;">
            <span id="gpu-status" style="color: #666;">正在连接...</span>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span id="auto-update-indicator" style="color: #2ed573; font-size: 10px;">●</span>
                <button id="gpu-refresh-btn" style="background: transparent; border: 1px solid #ddd; color: #666; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px;">刷新</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(container);
    console.log('GPU监控窗口已创建');
    
    // 绑定事件
    const closeBtn = container.querySelector('#gpu-close-btn');
    const refreshBtn = container.querySelector('#gpu-refresh-btn');
    
    closeBtn.addEventListener('click', function() {
        console.log('关闭按钮被点击');
        container.style.display = 'none';
        stopAutoUpdate(); // 停止自动更新
    });
    
    refreshBtn.addEventListener('click', function() {
        console.log('刷新按钮被点击');
        updateGPUInfo();
    });
    
    return container;
}

// 更新GPU信息
async function updateGPUInfo() {
    console.log('开始更新GPU信息...');
    
    const content = document.querySelector('#gpu-content');
    const status = document.querySelector('#gpu-status');
    
    if (!content || !status) {
        console.error('找不到content或status元素');
        return;
    }
    
    try {
        status.textContent = '连接中...';
        status.style.color = '#ffa502';
        
        console.log('发送API请求...');
        const response = await fetch('/api/gpu_status');
        console.log('API响应状态:', response.status);
        
        const data = await response.json();
        console.log('API返回数据:', data);
        
        if (data.success) {
            status.textContent = '在线';
            status.style.color = '#2ed573';
            
            if (data.gpus && data.gpus.length > 0) {
                console.log('检测到GPU:', data.gpus.length, '个');
                let html = '';
                data.gpus.forEach(gpu => {
                    const memPercent = gpu.memory.usage_percent;
                    const memColor = memPercent > 80 ? '#ff4757' : memPercent > 60 ? '#ffa502' : '#2ed573';
                    
                    html += `
                        <div style="background: white; border-radius: 8px; padding: 12px; margin-bottom: 8px; border: 1px solid #e1e8ed;">
                            <div style="font-weight: 600; margin-bottom: 8px; font-size: 13px; color: #2c3e50;">GPU ${gpu.id}: ${gpu.name}</div>
                            <div style="margin-bottom: 6px;">
                                <div style="font-size: 11px; color: #666; margin-bottom: 2px;">显存使用</div>
                                <div style="background: #e1e8ed; height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="height: 100%; width: ${memPercent}%; background: ${memColor}; transition: width 0.3s;"></div>
                                </div>
                                <div style="font-size: 11px; color: #333; margin-top: 2px; display: flex; justify-content: space-between;">
                                    <span>${gpu.memory.used_gb}GB / ${gpu.memory.total_gb}GB</span>
                                    <span style="font-weight: 600; color: ${memColor};">${memPercent}%</span>
                                </div>
                            </div>
                            ${gpu.utilization >= 0 ? `
                            <div style="margin-bottom: 6px;">
                                <div style="font-size: 11px; color: #666; margin-bottom: 2px;">GPU利用率</div>
                                <div style="background: #e1e8ed; height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="height: 100%; width: ${gpu.utilization}%; background: #5352ed; transition: width 0.3s;"></div>
                                </div>
                                <div style="font-size: 11px; color: #333; margin-top: 2px; text-align: right; font-weight: 600; color: #5352ed;">${gpu.utilization}%</div>
                            </div>
                            ` : ''}
                            <div style="display: flex; justify-content: space-between; font-size: 11px; color: #666; padding-top: 6px; border-top: 1px solid #f0f0f0;">
                                ${gpu.temperature >= 0 ? `<span style="display: flex; align-items: center; gap: 2px;"><span>🌡️</span><span>${gpu.temperature}°C</span></span>` : '<span></span>'}
                                ${gpu.power >= 0 ? `<span style="display: flex; align-items: center; gap: 2px;"><span>⚡</span><span>${gpu.power.toFixed(1)}W</span></span>` : '<span style="color: #bbb; font-size: 10px;">功耗不可用</span>'}
                            </div>
                        </div>
                    `;
                });
                content.innerHTML = html;
            } else {
                console.log('未检测到GPU');
                content.innerHTML = `
                    <div style="text-align: center; color: #999; padding: 20px;">
                        <div style="font-size: 24px; margin-bottom: 8px;">❌</div>
                        <div style="font-weight: 600; margin-bottom: 4px;">未检测到GPU</div>
                        <div style="font-size: 11px; color: #bbb;">可能没有安装NVIDIA GPU或驱动</div>
                    </div>
                `;
            }
        } else {
            throw new Error(data.error || '获取GPU信息失败');
        }
    } catch (error) {
        console.error('GPU监控更新失败:', error);
        status.textContent = '错误';
        status.style.color = '#ff4757';
        content.innerHTML = `
            <div style="text-align: center; color: #ff4757; padding: 20px;">
                <div style="font-size: 20px; margin-bottom: 8px;">⚠️</div>
                <div style="margin-bottom: 8px; font-weight: 600;">连接失败</div>
                <div style="font-size: 11px; color: #999;">${error.message}</div>
            </div>
        `;
    }
}

// 切换GPU监控窗口显示
function toggleGPUMonitor() {
    console.log('切换GPU监控窗口...');
    
    let window = document.querySelector('#gpu-monitor-window');
    
    if (!window) {
        console.log('窗口不存在，创建新窗口');
        window = createGPUMonitorWindow();
        updateGPUInfo(); // 首次显示时更新数据
        startAutoUpdate(); // 启动自动更新
    }
    
    if (window.style.display === 'none' || window.style.display === '') {
        console.log('显示窗口');
        window.style.display = 'block';
        updateGPUInfo(); // 显示时更新数据
        startAutoUpdate(); // 启动自动更新
    } else {
        console.log('隐藏窗口');
        window.style.display = 'none';
        stopAutoUpdate(); // 停止自动更新
    }
}

// 自动更新相关变量
let autoUpdateInterval = null;
const UPDATE_INTERVAL = 3000; // 3秒更新一次

// 启动自动更新
function startAutoUpdate() {
    if (autoUpdateInterval) {
        clearInterval(autoUpdateInterval);
    }
    
    autoUpdateInterval = setInterval(() => {
        const window = document.querySelector('#gpu-monitor-window');
        if (window && window.style.display !== 'none') {
            updateGPUInfo();
        } else {
            stopAutoUpdate(); // 窗口隐藏时停止更新
        }
    }, UPDATE_INTERVAL);
    
    console.log('GPU监控自动更新已启动，间隔:', UPDATE_INTERVAL, 'ms');
}

// 停止自动更新
function stopAutoUpdate() {
    if (autoUpdateInterval) {
        clearInterval(autoUpdateInterval);
        autoUpdateInterval = null;
        console.log('GPU监控自动更新已停止');
    }
}

// 全局快捷键
document.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.key === 'g') {
        e.preventDefault();
        console.log('快捷键Ctrl+G被按下');
        toggleGPUMonitor();
    }
});

// 立即尝试创建按钮（不等待DOM）
console.log('准备创建按钮...');
if (document.body) {
    console.log('document.body已存在，立即创建按钮');
    createTestButton();
} else {
    console.log('document.body不存在，等待DOM加载');
}

// DOM加载完成后创建按钮
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded事件触发');
    if (!document.getElementById('gpu-toggle-btn')) {
        console.log('按钮不存在，创建按钮');
        createTestButton();
    } else {
        console.log('按钮已存在');
    }
});

// 页面完全加载后再次检查
window.addEventListener('load', function() {
    console.log('window load事件触发');
    setTimeout(() => {
        if (!document.getElementById('gpu-toggle-btn')) {
            console.log('延迟检查：按钮不存在，创建按钮');
            createTestButton();
        } else {
            console.log('延迟检查：按钮已存在');
        }
    }, 500);
});

// 导出函数供全局使用
window.toggleGPUMonitor = toggleGPUMonitor;
window.createTestButton = createTestButton;

console.log('GPU监控脚本加载完成 - 所有弹窗已永久禁用 - 版本: 2025-08-08-v2');
