# GPU监控悬浮窗口

这是一个轻量级的GPU监控组件，可以在网页中显示实时的GPU状态信息。

## 功能特性

- 🖥️ **实时监控**: 显示GPU显存使用情况、利用率、温度
- 📍 **悬浮窗口**: 右上角悬浮显示，不影响页面使用
- � **自动更新**: 每3秒自动刷新GPU状态
- ⌨️ **快捷键**: Ctrl+G 快速切换显示/隐藏

## 使用方法

在HTML页面的`<head>`标签中添加：

```html
<!-- GPU监控组件 -->
<script src="gpu_monitor_debug.js"></script>
```

## 快捷键

- `Ctrl + G`: 切换GPU监控窗口显示/隐藏

## 系统要求

- **服务器**: 需要NVIDIA GPU和驱动
- **浏览器**: 现代浏览器（Chrome 60+, Firefox 55+等）

## API接口

需要后端提供 `/api/gpu_status` 接口返回GPU状态信息。

## 当前状态

✅ 已集成到以下页面：
- index.html (主页)
- video_index.html (视频模块介绍)
- image_index.html (图像模块介绍)
- infra_index.html (红外模块介绍)
- lidar_index.html (雷达模块介绍)
- trial.html (红外试用页面)
- image_trial.html (图像试用页面)
- lidar_trial.html (雷达试用页面)

✅ 已成功检测到：NVIDIA A100-SXM4-40GB

## 使用说明

在任何已集成的页面上：
1. 点击右上角的蓝色"🖥️ GPU"按钮
2. 或按 `Ctrl+G` 快捷键
3. 即可查看实时GPU状态监控
