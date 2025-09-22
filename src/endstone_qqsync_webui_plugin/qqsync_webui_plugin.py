"""
QQSync WebUI 插件
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from endstone.plugin import Plugin
import time

from .config import WebUIConfigManager
from .api import QQSyncInterface
from .server import WebUIServer


class qqsyncwebui(Plugin):
    """QQSync WebUI 插件主类"""
    api_version = "0.6"
    
    def __init__(self):
        super().__init__()
        self.webui_config = None
        self.qqsync_interface = None
        self.webui_server = None
        self._loop = None
        self._server_task = None
    
    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info("QQSync WebUI 插件正在加载...")
        
        # 初始化WebUI配置管理器
        self.webui_config = WebUIConfigManager(self.data_folder)
        # 为API兼容性添加别名
        self.config_manager = self.webui_config
        
        # 验证配置
        config_errors = self.webui_config.validate_config()
        if config_errors:
            self.logger.warning(f"配置验证发现问题: {config_errors}")
        
        # 初始化QQSync接口
        self.qqsync_interface = QQSyncInterface(self.server.plugin_manager)
        
        self.logger.info("QQSync WebUI 插件配置加载完成")
    
    def on_enable(self) -> None:
        """插件启用时调用"""
        self.logger.info("正在启用 QQSync WebUI 插件...")
        
        # 检查QQSync插件是否可用
        if not self.qqsync_interface.is_available():
            self.logger.error("QQSync插件未找到或未启用，WebUI插件无法正常工作")
            self.logger.error("请确保已安装并启用 endstone-qqsync-plugin")
            return
        
        # 获取QQSync插件信息
        plugin_info = self.qqsync_interface.get_plugin_info()
        self.logger.info(f"找到QQSync插件: {plugin_info}")
        
        # 初始化WebUI服务器
        host = self.webui_config.get_config('server.host', '127.0.0.1')
        port = self.webui_config.get_config('server.port', 8080)
        
        self.webui_server = WebUIServer(
            plugin=self,
            host=host,
            port=port
        )
        
        # 启动WebUI服务器
        self._start_webui_server()
        
        self.logger.info("QQSync WebUI 插件已启用")
    
    def on_disable(self) -> None:
        """插件禁用时调用"""
        self.logger.info("正在禁用 QQSync WebUI 插件...")
        
        # 停止WebUI服务器
        self._stop_webui_server()
        
        self.logger.info("QQSync WebUI 插件已禁用")
    
    def _start_webui_server(self):
        """启动WebUI服务器"""
        try:
            # 获取或创建事件循环
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            
            # 在新线程中运行异步服务器
            import threading
            
            def run_server():
                asyncio.set_event_loop(self._loop)
                self._loop.run_until_complete(self._run_webui_server())
            
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            
        except Exception as e:
            self.logger.error(f"启动WebUI服务器失败: {e}")
    
    async def _run_webui_server(self):
        """运行WebUI服务器的异步方法"""
        try:
            success = await self.webui_server.start()
            if success:
                host = self.webui_config.get_config('server.host', '127.0.0.1')
                port = self.webui_config.get_config('server.port', 8080)
                self.logger.info(f"WebUI服务器已启动: http://{host}:{port}")
                
                # 保持服务器运行
                while self.webui_server and self.webui_server.is_running:
                    await asyncio.sleep(1)
            else:
                self.logger.error("WebUI服务器启动失败")
                
        except Exception as e:
            self.logger.error(f"WebUI服务器运行时错误: {e}")
    
    def _stop_webui_server(self):
        """停止WebUI服务器"""
        try:
            if self.webui_server:
                # 创建停止任务
                if self._loop and self._loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        self.webui_server.stop(),
                        self._loop
                    )
                    future.result(timeout=10)  # 最多等待10秒
                
                self.webui_server = None
                self.logger.info("WebUI服务器已停止")
            
            if self._loop:
                self._loop = None
                
        except Exception as e:
            self.logger.error(f"停止WebUI服务器失败: {e}")
    
    def get_qqsync_plugin(self):
        """获取QQSync插件实例（供WebUI服务器使用）"""
        if self.qqsync_interface:
            return self.qqsync_interface._get_qqsync_plugin()
        return None
    
    def on_message_sent(self, sender: str, content: str, msg_type: str = 'chat', direction: str = 'game_to_qq'):
        """处理发送的消息（供QQSync插件调用）"""
        try:
            if self.webui_server:
                msg = {
                    'timestamp': int(time.time()),
                    'sender': sender,
                    'content': content,
                    'type': msg_type,
                    'direction': direction
                }
                self.webui_server._save_message_to_file(msg)
                self.logger.info(f"保存消息: {msg}")
        except Exception as e:
            self.logger.error(f"处理消息失败: {e}")
    
    def reload_config(self):
        """重新加载配置"""
        try:
            if self.webui_config:
                self.webui_config.load_config()
                
                # 验证配置
                config_errors = self.webui_config.validate_config()
                if config_errors:
                    self.logger.warning(f"配置验证发现问题: {config_errors}")
                else:
                    self.logger.info("配置重新加载完成")
                
                return True
        except Exception as e:
            self.logger.error(f"重新加载配置失败: {e}")
            return False
    
    def get_status(self) -> dict:
        """获取插件状态"""
        try:
            status = {
                'plugin_enabled': True,
                'webui_running': self.webui_server and self.webui_server.is_running,
                'qqsync_available': self.qqsync_interface and self.qqsync_interface.is_available(),
                'config_valid': len(self.webui_config.validate_config()) == 0 if self.webui_config else False
            }
            
            if self.qqsync_interface:
                status.update({
                    'qqsync_status': self.qqsync_interface.get_connection_status(),
                    'server_info': self.qqsync_interface.get_server_info()
                })
            
            return status
            
        except Exception as e:
            self.logger.error(f"获取状态失败: {e}")
            return {'error': str(e)}