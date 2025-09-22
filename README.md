# QQSync WebUI Plugin

为 [endstone-qqsync-plugin](https://github.com/yuexps/endstone-qqsync-plugin) 提供 Web 管理界面的扩展插件。

## 功能特性

- 🌐 **Web 管理界面** - 基于现代化 UI 的管理面板
- 📊 **实时监控** - 实时显示服务器状态、在线玩家、绑定用户等信息
- 👥 **用户管理** - 查看和管理QQ绑定用户，支持解绑操作
- ⚙️ **配置管理** - 通过Web界面查看QQSync插件配置

## 前置要求

- **必需**: [endstone-qqsync-plugin 0.1.0+](https://github.com/yuexps/endstone-qqsync-plugin) 已安装并启用
- **环境**: Python 3.11+ 和 Endstone 0.94+

## 安装

### 方法1: 通过 pip 安装
```bash
pip install endstone-qqsync-webui-plugin
```

### 方法2: 手动安装
1. 从 [Releases](https://github.com/yuexps/endstone-qqsync-webui-plugin/releases) 下载最新版本
2. 将 `.whl` 文件放到 Endstone 服务器的 `plugins` 目录
3. 重启服务器

## 配置

插件首次运行会在 `plugins/qqsync_webui_plugin/` 目录下生成配置文件 `webui_config.json`:

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 8080
  }
}
```

### 配置说明

- `server.host`: WebUI服务器监听地址（默认：127.0.0.1）
- `server.port`: WebUI服务器端口（默认：8080）

## 使用方法

1. 确保 QQSync 插件已正确安装和配置
2. 启动 Endstone 服务器
3. 在浏览器中访问 `http://127.0.0.1:8080`
4. 使用 Web 界面管理 QQSync 插件

### 功能页面

- **仪表板** (`/`): 显示系统状态、在线信息等概览
- **配置管理** (`/config`): 查看QQSync插件配置（只读）
- **用户管理** (`/users`): 管理QQ绑定用户，支持解绑操作

## 依赖关系

此插件通过 `self.server.plugin_manager.get_plugin('qqsync_plugin')` 调用主 QQSync 插件的功能，包括：

- 用户绑定管理
- 消息收发
- 统计数据
- WebSocket 连接管理

## 独立配置

WebUI 插件使用独立的配置文件系统，与主 QQSync 插件的配置完全分离：

- WebUI 配置: `plugins/qqsync_webui_plugin/webui_config.json`
- QQSync 配置: `plugins/qqsync_plugin/config.json`

## 故障排除

### 常见问题

1. **WebUI 无法访问**
   - 检查端口是否被占用
   - 确认防火墙设置
   - 查看插件是否正确启动

2. **显示"QQSync插件不可用"**
   - 确认 endstone-qqsync-plugin 0.1.0+ 已安装
   - 检查插件是否正确启用
   - 查看 QQSync 插件日志

3. **功能异常**
   - 检查 QQSync 插件是否正常工作
   - 查看 WebUI 插件日志
   - 重启插件或服务器

## 许可证

MIT License

## 相关链接

- [主QQSync插件](https://github.com/yuexps/endstone-qqsync-plugin)
- [Endstone 文档](https://docs.endstone.dev/)