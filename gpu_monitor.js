/**
 * GPU 监控悬浮窗口
 * 可以在任何页面中引用，实时显示GPU状态
 */

class GPUMonitor {
    constructor() {
        this.isVisible = false;
        this.isMinimized = false;
        this.updateInterval = null;
        this.updateFrequency = 2000; // 2秒更新一次
        this.apiEndpoint = '/api/gpu_status';
        
        // 创建悬浮窗口
        this.createFloatingWindow();
        
        // 绑定事件
        this.bindEvents();
        
        // 从localStorage恢复状态
        this.restoreState();
        
        // 开始监控
        this.startMonitoring();
    }
    
    createFloatingWindow() {
        // 创建主容器
        this.container = document.createElement('div');
        this.container.id = 'gpu-monitor-container';
        this.container.className = 'gpu-monitor-container';
        
        // 创建标题栏
        const header = document.createElement('div');
        header.className = 'gpu-monitor-header';
        header.innerHTML = `
            <div class="gpu-monitor-title">
                <span class="gpu-icon">🖥️</span>
                <span>GPU 监控</span>
            </div>
            <div class="gpu-monitor-controls">
                <button class="gpu-monitor-btn minimize-btn" title="最小化">－</button>
                <button class="gpu-monitor-btn close-btn" title="关闭">×</button>
            </div>
        `;
        
        // 创建内容区域
        this.content = document.createElement('div');
        this.content.className = 'gpu-monitor-content';
        this.content.innerHTML = `
            <div class="gpu-monitor-loading">
                <div class="loading-spinner"></div>
                <span>正在获取GPU信息...</span>
            </div>
        `;
        
        // 创建底部控制区
        const footer = document.createElement('div');
        footer.className = 'gpu-monitor-footer';
        footer.innerHTML = `
            <div class="gpu-monitor-status">
                <span class="status-indicator offline"></span>
                <span class="status-text">离线</span>
            </div>
            <div class="gpu-monitor-refresh">
                <button class="gpu-monitor-btn refresh-btn" title="手动刷新">🔄</button>
                <select class="update-frequency" title="更新频率">
                    <option value="1000">1秒</option>
                    <option value="2000" selected>2秒</option>
                    <option value="5000">5秒</option>
                    <option value="10000">10秒</option>
                </select>
            </div>
        `;
        
        // 组装窗口
        this.container.appendChild(header);
        this.container.appendChild(this.content);
        this.container.appendChild(footer);
        
        // 添加到页面
        document.body.appendChild(this.container);
        
        // 使窗口可拖拽
        this.makeDraggable(header);
    }
    
    bindEvents() {
        // 最小化按钮
        this.container.querySelector('.minimize-btn').addEventListener('click', () => {
            this.toggleMinimize();
        });
        
        // 关闭按钮
        this.container.querySelector('.close-btn').addEventListener('click', () => {
            this.hide();
        });
        
        // 刷新按钮
        this.container.querySelector('.refresh-btn').addEventListener('click', () => {
            this.updateGPUStatus();
        });
        
        // 更新频率选择
        this.container.querySelector('.update-frequency').addEventListener('change', (e) => {
            this.updateFrequency = parseInt(e.target.value);
            this.restartMonitoring();
            this.saveState();
        });
        
        // 键盘快捷键 (Ctrl+G 切换显示)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'g') {
                e.preventDefault();
                this.toggle();
            }
        });
    }
    
    makeDraggable(header) {
        let isDragging = false;
        let startX, startY, startLeft, startTop;
        
        header.addEventListener('mousedown', (e) => {
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            
            const rect = this.container.getBoundingClientRect();
            startLeft = rect.left;
            startTop = rect.top;
            
            header.style.cursor = 'grabbing';
            e.preventDefault();
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            
            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;
            
            let newLeft = startLeft + deltaX;
            let newTop = startTop + deltaY;
            
            // 边界检查
            const containerRect = this.container.getBoundingClientRect();
            const maxLeft = window.innerWidth - containerRect.width;
            const maxTop = window.innerHeight - containerRect.height;
            
            newLeft = Math.max(0, Math.min(newLeft, maxLeft));
            newTop = Math.max(0, Math.min(newTop, maxTop));
            
            this.container.style.left = newLeft + 'px';
            this.container.style.top = newTop + 'px';
            this.container.style.right = 'auto';
            this.container.style.bottom = 'auto';
        });
        
        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                header.style.cursor = 'grab';
                this.saveState();
            }
        });
        
        header.style.cursor = 'grab';
    }
    
    async updateGPUStatus() {
        try {
            const response = await fetch(this.apiEndpoint);
            const data = await response.json();
            
            if (data.success) {
                this.renderGPUData(data);
                this.updateStatus('online', '在线');
            } else {
                this.renderError(data.error || '获取GPU信息失败');
                this.updateStatus('error', '错误');
            }
        } catch (error) {
            console.error('GPU监控更新失败:', error);
            this.renderError('网络连接失败');
            this.updateStatus('offline', '离线');
        }
    }
    
    renderGPUData(data) {
        if (!data.gpus || data.gpus.length === 0) {
            this.content.innerHTML = `
                <div class="gpu-monitor-no-data">
                    <span>❌ 未检测到GPU</span>
                </div>
            `;
            return;
        }
        
        let html = '';
        data.gpus.forEach((gpu, index) => {
            const memoryPercent = gpu.memory.usage_percent;
            const memoryColor = memoryPercent > 80 ? '#ff4757' : memoryPercent > 60 ? '#ffa502' : '#2ed573';
            
            html += `
                <div class="gpu-card">
                    <div class="gpu-card-header">
                        <span class="gpu-name">GPU ${gpu.id}: ${gpu.name}</span>
                    </div>
                    <div class="gpu-metrics">
                        <div class="metric">
                            <div class="metric-label">显存使用</div>
                            <div class="metric-value">
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${memoryPercent}%; background-color: ${memoryColor}"></div>
                                </div>
                                <span class="metric-text">${gpu.memory.used_gb}GB / ${gpu.memory.total_gb}GB (${memoryPercent}%)</span>
                            </div>
                        </div>
                        ${gpu.utilization >= 0 ? `
                        <div class="metric">
                            <div class="metric-label">GPU利用率</div>
                            <div class="metric-value">
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${gpu.utilization}%; background-color: #5352ed"></div>
                                </div>
                                <span class="metric-text">${gpu.utilization}%</span>
                            </div>
                        </div>
                        ` : ''}
                        <div class="metric-row">
                            ${gpu.temperature >= 0 ? `
                            <div class="metric-small">
                                <span class="metric-icon">🌡️</span>
                                <span>${gpu.temperature}°C</span>
                            </div>
                            ` : ''}
                            ${gpu.power >= 0 ? `
                            <div class="metric-small">
                                <span class="metric-icon">⚡</span>
                                <span>${gpu.power.toFixed(1)}W</span>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        });
        
        this.content.innerHTML = html;
    }
    
    renderError(message) {
        this.content.innerHTML = `
            <div class="gpu-monitor-error">
                <span class="error-icon">⚠️</span>
                <span class="error-message">${message}</span>
            </div>
        `;
    }
    
    updateStatus(status, text) {
        const indicator = this.container.querySelector('.status-indicator');
        const statusText = this.container.querySelector('.status-text');
        
        indicator.className = `status-indicator ${status}`;
        statusText.textContent = text;
    }
    
    startMonitoring() {
        this.updateGPUStatus(); // 立即更新一次
        this.updateInterval = setInterval(() => {
            this.updateGPUStatus();
        }, this.updateFrequency);
    }
    
    stopMonitoring() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
    
    restartMonitoring() {
        this.stopMonitoring();
        this.startMonitoring();
    }
    
    show() {
        this.isVisible = true;
        this.container.style.display = 'block';
        this.saveState();
        
        if (!this.updateInterval) {
            this.startMonitoring();
        }
    }
    
    hide() {
        this.isVisible = false;
        this.container.style.display = 'none';
        this.saveState();
        this.stopMonitoring();
    }
    
    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }
    
    toggleMinimize() {
        this.isMinimized = !this.isMinimized;
        const content = this.container.querySelector('.gpu-monitor-content');
        const footer = this.container.querySelector('.gpu-monitor-footer');
        const minimizeBtn = this.container.querySelector('.minimize-btn');
        
        if (this.isMinimized) {
            content.style.display = 'none';
            footer.style.display = 'none';
            minimizeBtn.textContent = '□';
            minimizeBtn.title = '还原';
            this.container.classList.add('minimized');
        } else {
            content.style.display = 'block';
            footer.style.display = 'flex';
            minimizeBtn.textContent = '－';
            minimizeBtn.title = '最小化';
            this.container.classList.remove('minimized');
        }
        
        this.saveState();
    }
    
    saveState() {
        const state = {
            isVisible: this.isVisible,
            isMinimized: this.isMinimized,
            updateFrequency: this.updateFrequency,
            position: {
                left: this.container.style.left,
                top: this.container.style.top,
                right: this.container.style.right,
                bottom: this.container.style.bottom
            }
        };
        
        localStorage.setItem('gpu-monitor-state', JSON.stringify(state));
    }
    
    restoreState() {
        try {
            const savedState = localStorage.getItem('gpu-monitor-state');
            if (savedState) {
                const state = JSON.parse(savedState);
                
                // 恢复可见性
                if (state.isVisible) {
                    this.show();
                } else {
                    this.hide();
                }
                
                // 恢复最小化状态
                if (state.isMinimized) {
                    this.toggleMinimize();
                }
                
                // 恢复更新频率
                if (state.updateFrequency) {
                    this.updateFrequency = state.updateFrequency;
                    const frequencySelect = this.container.querySelector('.update-frequency');
                    frequencySelect.value = state.updateFrequency;
                }
                
                // 恢复位置
                if (state.position) {
                    if (state.position.left) this.container.style.left = state.position.left;
                    if (state.position.top) this.container.style.top = state.position.top;
                    if (state.position.right) this.container.style.right = state.position.right;
                    if (state.position.bottom) this.container.style.bottom = state.position.bottom;
                }
            }
        } catch (error) {
            console.warn('恢复GPU监控状态失败:', error);
        }
    }
    
    destroy() {
        this.stopMonitoring();
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
    }
}

// 创建全局切换函数
window.toggleGPUMonitor = function() {
    if (window.gpuMonitor) {
        window.gpuMonitor.toggle();
    }
};

// 在页面加载完成后自动初始化
document.addEventListener('DOMContentLoaded', function() {
    // 延迟初始化，确保页面完全加载
    setTimeout(() => {
        if (!window.gpuMonitor) {
            window.gpuMonitor = new GPUMonitor();
        }
    }, 1000);
});

// 页面卸载时清理
window.addEventListener('beforeunload', function() {
    if (window.gpuMonitor) {
        window.gpuMonitor.destroy();
    }
});
