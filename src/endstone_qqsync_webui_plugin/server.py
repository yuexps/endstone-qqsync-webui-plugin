"""
WebUI服务器模块
基于aiohttp实现的异步Web服务器
"""

import asyncio
import json
import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# 直接从lib目录导入
import sys
from pathlib import Path

# 添加lib路径到sys.path
lib_path = Path(__file__).parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

# 尝试导入aiohttp
try:
    import aiohttp
    from aiohttp import web, WSMsgType
    from aiohttp.web_response import Response
    from aiohttp.web_request import Request
    AIOHTTP_AVAILABLE = True
except ImportError as e:
    print(f"aiohttp导入失败: {e}")
    AIOHTTP_AVAILABLE = False
    web = None
    WSMsgType = None
    Response = None
    Request = None

# 尝试导入jinja2
try:
    import jinja2
    from jinja2 import Environment, FileSystemLoader
    JINJA2_AVAILABLE = True
except ImportError as e:
    print(f"jinja2导入失败: {e}")
    JINJA2_AVAILABLE = False
    Environment = None
    FileSystemLoader = None


class WebUIServer:
    """WebUI服务器"""
    
    def __init__(self, plugin, host: str = "127.0.0.1", port: int = 8080):
        self.plugin = plugin
        webui_config = getattr(plugin, 'webui_config', None)
        if webui_config:
            config_host = webui_config.get_config('server.host', host)
            config_port = webui_config.get_config('server.port', port)
            self.host = config_host
            self.port = config_port
        else:
            self.host = host
            self.port = port
        self.logger = plugin.logger
        self.app = None
        self.runner = None
        self.site = None
        self.is_running = False
        
        # 获取QQSync接口和WebUI配置
        self.qqsync_interface = getattr(plugin, 'qqsync_interface', None)
        self.webui_config = getattr(plugin, 'webui_config', None)
        
        # 设置消息存储目录
        self.message_storage_dir = plugin.data_folder / "msg"
        self.message_storage_dir.mkdir(exist_ok=True)
        
        # 检查依赖
        if not AIOHTTP_AVAILABLE:
            self.logger.error("WebUI需要aiohttp依赖")
            return
            
        if not JINJA2_AVAILABLE:
            self.logger.error("WebUI需要jinja2依赖")
            return
            
        # 设置模板引擎
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )
        def datetime_filter(value, format="%Y-%m-%d %H:%M:%S"):
            import datetime
            if isinstance(value, (int, float)):
                # 时间戳
                return datetime.datetime.fromtimestamp(value).strftime(format)
            elif isinstance(value, datetime.datetime):
                return value.strftime(format)
            elif isinstance(value, str):
                try:
                    dt = datetime.datetime.fromisoformat(value)
                    return dt.strftime(format)
                except Exception:
                    return value
            return str(value)
        self.jinja_env.filters['datetime'] = datetime_filter
        
        # 静态文件目录
        self.static_dir = Path(__file__).parent / "static"
        self.logger.debug(f"静态文件目录: {self.static_dir}")
        self.logger.debug(f"静态文件目录存在: {self.static_dir.exists()}")
        
        self._setup_app()
    
    def _setup_app(self):
        """设置Web应用"""
        if not AIOHTTP_AVAILABLE or not JINJA2_AVAILABLE:
            return
            
        self.app = web.Application()
        
        # 设置路由
        self._setup_routes()
        
        # 设置中间件
        self._setup_middleware()
    
    def _setup_routes(self):
        """设置路由"""
        # 静态文件路由 - 注意路径要以斜杠结尾
        self.app.router.add_static('/static', path=str(self.static_dir), name='static', show_index=False)
        
        # 页面路由
        self.app.router.add_get('/', self.dashboard_page)
        self.app.router.add_get('/dashboard', self.dashboard_page)
        self.app.router.add_get('/config', self.config_page)
        self.app.router.add_get('/users', self.users_page)
        
        # favicon.ico 处理
        self.app.router.add_get('/favicon.ico', self.favicon_handler)
        
        # 处理其他常见的浏览器请求
        self.app.router.add_get('/robots.txt', self.robots_handler)
        self.app.router.add_get('/sitemap.xml', self.sitemap_handler)
        
        # API路由
        self.app.router.add_get('/api/status', self.api_status)
        self.app.router.add_get('/api/debug', self.api_debug)  # 调试信息
        self.app.router.add_get('/api/dashboard', self.api_dashboard)
        self.app.router.add_get('/api/config', self.api_get_config)
        self.app.router.add_post('/api/config', self.api_set_config)
        self.app.router.add_get('/api/users', self.api_get_users)
        self.app.router.add_get('/api/users/{player_name}', self.api_get_user_info)
        self.app.router.add_get('/api/users/{player_name}/stats', self.api_get_user_stats)
        self.app.router.add_post('/api/users/{player_name}/unbind', self.api_unbind_user)
        self.app.router.add_post('/api/users/{player_name}/ban', self.api_ban_user)
        self.app.router.add_post('/api/users/{player_name}/unban', self.api_unban_user)
        self.app.router.add_get('/api/stats', self.api_get_statistics)
        self.app.router.add_post('/api/websocket/restart', self.api_restart_websocket)
        self.app.router.add_post('/api/messages/send', self.api_send_message)
        self.app.router.add_post('/api/messages/send_game', self.api_send_game_message)
        self.app.router.add_post('/api/messages/console', self.api_send_console_command)
        self.app.router.add_get('/api/messages/stats', self.api_get_message_stats)
        
        # 通用404处理器 - 必须放在最后
        self.app.router.add_route('*', '/{path:.*}', self.not_found_handler)
    
    def _setup_middleware(self):
        """设置中间件"""
        @web.middleware
        async def cors_handler(request, handler):
            """CORS处理"""
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            return response
        
        @web.middleware
        async def error_handler(request, handler):
            """错误处理"""
            try:
                return await handler(request)
            except web.HTTPNotFound:
                # 404错误已由not_found_handler处理，不需要在这里记录
                raise
            except Exception as e:
                self.logger.error(f"WebUI请求处理错误: {e} - {request.method} {request.path_qs}")
                return web.json_response({
                    'success': False,
                    'error': str(e)
                }, status=500)
        
        self.app.middlewares.append(cors_handler)
        self.app.middlewares.append(error_handler)
    
    async def start(self):
        """启动Web服务器"""
        if not AIOHTTP_AVAILABLE:
            self.logger.error("无法启动WebUI: aiohttp未安装")
            return False
            
        if self.is_running:
            self.logger.warning("WebUI服务器已在运行")
            return True
            
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            self.is_running = True
            # 启动成功日志由主插件记录，避免重复
            return True
            
        except Exception as e:
            self.logger.error(f"启动WebUI服务器失败: {e}")
            return False
    
    async def stop(self):
        """停止Web服务器"""
        if not self.is_running:
            return
            
        try:
            if self.site:
                await self.site.stop()
                self.site = None
                
            if self.runner:
                await self.runner.cleanup()
                self.runner = None
                
            self.is_running = False
            self.logger.info("WebUI服务器已停止")
            
        except Exception as e:
            self.logger.error(f"停止WebUI服务器失败: {e}")
    
    def render_template(self, template_name: str, **context) -> str:
        """渲染模板"""
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)
    
    # 页面路由处理器
    async def dashboard_page(self, request):
        """仪表板页面"""
        try:
            # 检查QQSync插件是否可用
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                error_msg = "QQSync插件未找到或未启用，请先安装并启用 endstone-qqsync-plugin"
                html = self.render_template('dashboard.html',
                    error=error_msg,
                    plugin_status={'enabled': False},
                    websocket_status={'connected': False},
                    online_players_count=0,
                    bound_users_count=0,
                    recent_messages=[]
                )
                return web.Response(text=html, content_type='text/html')
            
            # 获取服务器信息
            server_info = self.qqsync_interface.get_server_info()
            
            # 获取插件状态
            plugin_status = {
                'enabled': self.qqsync_interface.is_available()
            }
            
            # 获取WebSocket状态
            connection_status = self.qqsync_interface.get_connection_status()
            websocket_status = {
                'connected': connection_status.get('websocket_connected', False)
            }
            
            # 获取在线玩家数量
            online_players_count = server_info.get('online_players_count', 0)
            
            # 获取绑定用户数量
            bound_users_count = server_info.get('bound_users_count', 0)
            
            # 获取最近历史消息（从文件读取）
            recent_messages = self._get_recent_messages_from_file(limit=50)
            
            html = self.render_template('dashboard.html',
                plugin_status=plugin_status,
                websocket_status=websocket_status,
                online_players_count=online_players_count,
                bound_users_count=bound_users_count,
                recent_messages=recent_messages
            )
            
            return web.Response(text=html, content_type='text/html')
            
        except Exception as e:
            self.logger.error(f"仪表板页面渲染失败: {e}")
            return web.Response(text="页面加载失败", status=500)
    
    async def config_page(self, request):
        """配置页面"""
        try:
            html = self.render_template('config.html')
            return web.Response(text=html, content_type='text/html')
        except Exception as e:
            self.logger.error(f"配置页面渲染失败: {e}")
            return web.Response(text=f"页面加载失败: {e}", status=500)
    
    async def users_page(self, request):
        """用户管理页面"""
        try:
            html = self.render_template('users.html')
            return web.Response(text=html, content_type='text/html')
        except Exception as e:
            self.logger.error(f"用户管理页面渲染失败: {e}")
            return web.Response(text=f"页面加载失败: {e}", status=500)

    async def favicon_handler(self, request):
        """处理favicon.ico请求"""
        # 返回204 No Content，避免404错误
        return web.Response(status=204)
    
    async def robots_handler(self, request):
        """处理robots.txt请求"""
        return web.Response(text="User-agent: *\nDisallow: /", content_type='text/plain')
    
    async def sitemap_handler(self, request):
        """处理sitemap.xml请求"""
        return web.Response(status=204)
    
    async def not_found_handler(self, request):
        """通用404处理器"""
        path = request.path
        method = request.method
        
        # 记录详细的404信息
        self.logger.warning(f"404 Not Found: {method} {path}")
        
        # 对于API请求，返回JSON响应
        if path.startswith('/api/'):
            return web.json_response({
                'success': False,
                'error': 'API endpoint not found',
                'path': path
            }, status=404)
        
        # 对于页面请求，重定向到首页或返回错误页面
        if method == 'GET' and not path.startswith('/static/'):
            # 重定向到首页
            return web.HTTPFound('/')
        
        # 其他请求返回204（比如一些浏览器的自动请求）
        return web.Response(status=204)
    
    # API路由处理器
    async def api_status(self, request):
        """获取系统状态"""
        try:
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                status = {
                    'plugin_enabled': False,
                    'websocket_connected': False,
                    'online_players': 0,
                    'bound_users': 0,
                    'timestamp': datetime.now().isoformat(),
                    'error': 'QQSync插件不可用'
                }
                return web.json_response(status)
            
            # 获取服务器信息
            server_info = self.qqsync_interface.get_server_info()
            connection_status = self.qqsync_interface.get_connection_status()
            
            status = {
                'plugin_enabled': True,
                'websocket_connected': connection_status.get('websocket_connected', False),
                'bot_online': connection_status.get('bot_online', False),
                'online_players': server_info.get('online_players_count', 0),
                'bound_users': server_info.get('bound_users_count', 0),
                'timestamp': datetime.now().isoformat(),
                'reconnect_attempts': connection_status.get('reconnect_attempts', 0)
            }
            
            return web.json_response(status)
            
        except Exception as e:
            self.logger.error(f"获取状态失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_dashboard(self, request):
        """获取仪表板数据"""
        try:
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                return web.json_response({
                    'error': 'QQSync插件不可用',
                    'stats': {
                        'online_players': 0,
                        'bound_users': 0,
                        'total_messages': 0,
                        'uptime': '0分钟',
                        'websocket_status': 'disconnected',
                        'config_complete': False
                    }
                }, status=503)
            
            # 获取服务器信息
            server_info = self.qqsync_interface.get_server_info()
            connection_status = server_info.get('connection_status', {})
            
            # 获取在线玩家列表
            online_players_list = server_info.get('online_players', [])
            
            # 获取WebSocket连接状态
            ws_status = 'connected' if connection_status.get('websocket_connected', False) else 'disconnected'
            ws_last_ping = connection_status.get('last_ping')
            
            # 获取QQSync配置状态
            qqsync_config = self.qqsync_interface.get_config()
            config_status = {
                'target_group_set': bool(qqsync_config.get('target_group')),
                'napcat_ws_set': bool(qqsync_config.get('napcat_ws')),
                'websocket_configured': bool(qqsync_config.get('napcat_ws'))
            }
            
            # 获取统计数据
            statistics = self.qqsync_interface.get_statistics(7)  # 最近7天
            total_messages = statistics.get('total_messages', 0)
            
            data = {
                'stats': {
                    'online_players': server_info.get('online_players_count', 0),
                    'bound_users': server_info.get('bound_users_count', 0),
                    'total_messages': total_messages,
                    'uptime': self._get_uptime(),
                    'websocket_status': ws_status,
                    'config_complete': all(config_status.values())
                },
                'online_players_list': online_players_list,
                'websocket_info': {
                    'status': ws_status,
                    'last_ping': ws_last_ping,
                    'reconnect_attempts': connection_status.get('reconnect_attempts', 0)
                },
                'config_status': config_status,
                'recent_messages': self._get_recent_messages_from_file(limit=50),
                'system_info': {
                    'plugin_version': '1.0.0',
                    'api_version': '1.0',
                    'last_updated': datetime.now().isoformat(),
                    'qqsync_plugin_info': self.qqsync_interface.get_plugin_info()
                }
            }
            
            return web.json_response(data)
            
        except Exception as e:
            self.logger.error(f"获取仪表板数据失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_debug(self, request):
        """调试信息API"""
        try:
            debug_info = {
                'plugin_info': {
                    'has_plugin': hasattr(self, 'plugin') and self.plugin is not None,
                    'plugin_type': type(self.plugin).__name__ if hasattr(self, 'plugin') else None,
                    'has_config_manager': hasattr(self.plugin, 'config_manager') if hasattr(self, 'plugin') else False,
                    'config_manager_type': type(self.plugin.config_manager).__name__ if hasattr(self, 'plugin') and hasattr(self.plugin, 'config_manager') else None,
                    'has_webui_config': hasattr(self.plugin, 'webui_config') if hasattr(self, 'plugin') else False,
                    'webui_config_type': type(self.plugin.webui_config).__name__ if hasattr(self, 'plugin') and hasattr(self.plugin, 'webui_config') else None,
                },
                'qqsync_info': {
                    'has_qqsync_interface': hasattr(self, 'qqsync_interface') and self.qqsync_interface is not None,
                    'qqsync_available': self.qqsync_interface.is_available() if hasattr(self, 'qqsync_interface') and self.qqsync_interface else False,
                    'qqsync_plugin_info': None,
                    'qqsync_config_manager_available': False,
                },
                'server_info': {
                    'has_webui_config': hasattr(self, 'webui_config') and self.webui_config is not None,
                    'server_running': hasattr(self, 'is_running') and self.is_running,
                },
                'config_test': {
                    'webui_config_access': False,
                    'qqsync_config_access': False,
                    'webui_config_error': None,
                    'qqsync_config_error': None,
                }
            }
            
            # 测试QQSync接口
            if hasattr(self, 'qqsync_interface') and self.qqsync_interface:
                try:
                    debug_info['qqsync_info']['qqsync_plugin_info'] = self.qqsync_interface.get_plugin_info()
                    
                    # 测试QQSync配置访问
                    qqsync_plugin = self.qqsync_interface._get_qqsync_plugin()
                    if qqsync_plugin and hasattr(qqsync_plugin, 'config_manager'):
                        debug_info['qqsync_info']['qqsync_config_manager_available'] = True
                        debug_info['config_test']['qqsync_config_access'] = True
                        debug_info['config_test']['qqsync_sample_config'] = self.qqsync_interface.get_config('target_group')
                except Exception as e:
                    debug_info['config_test']['qqsync_config_error'] = str(e)
            
            # 测试WebUI配置管理器访问
            try:
                if hasattr(self.plugin, 'config_manager') and self.plugin.config_manager:
                    debug_info['config_test']['webui_config_access'] = True
                    debug_info['config_test']['webui_sample_config'] = self.plugin.config_manager.get_config('server.host', 'N/A')
            except Exception as e:
                debug_info['config_test']['webui_config_error'] = str(e)
            
            return web.json_response(debug_info)
            
        except Exception as e:
            self.logger.error(f"获取调试信息失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_config(self, request):
        """获取配置"""
        try:
            # 获取QQSync插件配置
            qqsync_config = {}
            if self.qqsync_interface and self.qqsync_interface.is_available():
                qqsync_config = self.qqsync_interface.get_config()
            
            # 获取WebUI配置
            webui_config = {}
            if self.webui_config:
                webui_config = self.webui_config.get_all_config()
            
            # 合并配置，保持向后兼容
            config = {
                # QQSync插件配置
                'napcat_ws': qqsync_config.get('napcat_ws', 'ws://127.0.0.1:3001'),
                'access_token': qqsync_config.get('access_token', ''),
                'target_group': qqsync_config.get('target_group', ''),
                'admins': qqsync_config.get('admins', []),
                'enable_qq_to_game': qqsync_config.get('enable_qq_to_game', True),
                'enable_game_to_qq': qqsync_config.get('enable_game_to_qq', True),
                'force_bind_qq': qqsync_config.get('force_bind_qq', True),
                'sync_group_card': qqsync_config.get('sync_group_card', True),
                'check_group_member': qqsync_config.get('check_group_member', True),
                'chat_count_limit': qqsync_config.get('chat_count_limit', 20),
                'chat_ban_time': qqsync_config.get('chat_ban_time', 300),
                'api_qq_enable': qqsync_config.get('api_qq_enable', False),
                
                # WebUI配置
                'webui': webui_config,
            }
            
            return web.json_response(config)
            
        except Exception as e:
            self.logger.error(f"获取配置失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_set_config(self, request):
        """设置配置"""
        try:
            # 检查配置管理器是否可用
            if not hasattr(self.plugin, 'config_manager') or self.plugin.config_manager is None:
                self.logger.error("配置管理器不可用 - config_manager属性不存在或为None")
                return web.json_response({'error': '配置管理器不可用，请检查插件状态'}, status=500)
            
            # 获取并验证请求数据
            try:
                data = await request.json()
            except Exception as e:
                self.logger.error(f"解析配置数据失败: {e}")
                return web.json_response({'error': f'配置数据格式错误: {e}'}, status=400)
            
            if not isinstance(data, dict):
                return web.json_response({'error': '配置数据必须是JSON对象'}, status=400)
            
            # 获取客户端IP
            client_ip = request.remote
            
            # 分离WebUI配置和QQSync配置
            webui_config = {}
            qqsync_config = {}
            
            # QQSync主插件配置项列表
            qqsync_config_keys = {
                'napcat_ws', 'access_token', 'target_group', 'admins',
                'enable_qq_to_game', 'enable_game_to_qq', 'force_bind_qq',
                'sync_group_card', 'check_group_member', 'chat_count_limit',
                'chat_ban_time', 'api_qq_enable'
            }
            
            # 分类配置项
            for key, value in data.items():
                if key in qqsync_config_keys:
                    qqsync_config[key] = value
                elif key.startswith('webui.'):
                    webui_config[key] = value
                else:
                    # 默认归类为QQSync配置（向后兼容）
                    qqsync_config[key] = value
            
            success_count = 0
            error_messages = []
            
            # 更新QQSync主插件配置
            if qqsync_config and self.qqsync_interface and self.qqsync_interface.is_available():
                try:
                    results = self.qqsync_interface.update_config(qqsync_config)
                    for key, success in results.items():
                        if success:
                            success_count += 1
                            self.logger.info(f"QQSync配置已更新: {key}")
                        else:
                            error_messages.append(f"QQSync配置更新失败: {key}")
                except Exception as e:
                    self.logger.error(f"更新QQSync配置失败: {e}")
                    error_messages.append(f"QQSync配置更新失败: {e}")
            elif qqsync_config:
                error_messages.append("QQSync插件不可用，无法更新主插件配置")
            
            # 更新WebUI配置
            if webui_config and hasattr(self.plugin, 'config_manager'):
                try:
                    for key, value in webui_config.items():
                        self.plugin.config_manager.set_config(key, value)
                        success_count += 1
                    
                    # 保存WebUI配置
                    self.plugin.config_manager.save_config()
                    self.logger.info(f"WebUI配置已更新: {list(webui_config.keys())}")
                    
                except Exception as e:
                    self.logger.error(f"保存WebUI配置失败: {e}")
                    error_messages.append(f"WebUI配置保存失败: {e}")
            
            # 记录配置变更到审计日志
            if hasattr(self.plugin, 'data_manager') and hasattr(self.plugin.data_manager, 'audit_logger'):
                try:
                    for key, value in data.items():
                        # 记录审计日志
                        self.plugin.data_manager.audit_logger.log_config_change(
                            config_key=key,
                            old_value="",  # 可以后续优化获取旧值
                            new_value=value,
                            operator="Web管理员",
                            ip_address=client_ip
                        )
                except Exception as e:
                    self.logger.warning(f"记录审计日志失败: {e}")
            
            # 返回结果
            if error_messages:
                if success_count > 0:
                    message = f"部分配置保存成功({success_count}项)，但有错误: {'; '.join(error_messages)}"
                    return web.json_response({'success': False, 'message': message, 'partial_success': True}, status=207)
                else:
                    message = f"配置保存失败: {'; '.join(error_messages)}"
                    return web.json_response({'error': message}, status=500)
            else:
                self.logger.info(f"所有配置已成功保存({success_count}项): {list(data.keys())}")
                return web.json_response({'success': True, 'message': f'配置已保存({success_count}项)'})
            
        except Exception as e:
            self.logger.error(f"设置配置时发生未预期错误: {e}", exc_info=True)
            return web.json_response({'error': f'服务器内部错误: {e}'}, status=500)
    
    async def api_get_users(self, request):
        """获取用户列表"""
        try:
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                return web.json_response({
                    'error': 'QQSync插件不可用',
                    'users': []
                }, status=503)
            
            users = self.qqsync_interface.get_users()
            return web.json_response({'users': users})
            
        except Exception as e:
            self.logger.error(f"获取用户列表失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_user_stats(self, request):
        """获取单个用户的统计信息"""
        try:
            player_name = request.match_info.get('player_name')
            if not player_name:
                return web.json_response({'error': '未提供玩家名称'}, status=400)
            
            if not hasattr(self.plugin, 'data_manager'):
                return web.json_response({'error': '数据管理器不可用'}, status=500)
            
            # 获取用户绑定信息
            bindings = self.plugin.data_manager.get_all_bindings()
            if player_name not in bindings:
                return web.json_response({'error': '用户不存在'}, status=404)
            
            user_info = bindings[player_name]
            
            # 获取统计数据
            stats_data = self.plugin.data_manager.get_statistics()
            user_stats = {
                'player_name': player_name,
                'qq_number': user_info.get('qq_number'),
                'bind_time': user_info.get('bind_time'),
                'is_online': player_name in [p.name for p in self.plugin.server.online_players] if hasattr(self.plugin, 'server') and self.plugin.server else False,
                'message_count': 0,
                'first_login': None,
                'last_login': None,
                'online_time': 0,
                'bind_duration': 0
            }
            
            # 计算绑定时长
            if user_info.get('bind_time'):
                try:
                    from datetime import datetime
                    if isinstance(user_info['bind_time'], str):
                        bind_time = datetime.fromisoformat(user_info['bind_time'].replace('Z', '+00:00'))
                    else:
                        bind_time = datetime.fromtimestamp(user_info['bind_time'])
                    
                    user_stats['bind_duration'] = int((datetime.now() - bind_time).total_seconds())
                except:
                    pass
            
            # 从统计数据中查找用户相关数据
            for date, date_stats in stats_data.get('daily', {}).items():
                for user_data in date_stats.get('users', []):
                    if user_data.get('player_name') == player_name:
                        user_stats['message_count'] += user_data.get('message_count', 0)
                        
                        # 更新首次和最后登录时间
                        login_time = user_data.get('last_active')
                        if login_time:
                            if not user_stats['first_login'] or login_time < user_stats['first_login']:
                                user_stats['first_login'] = login_time
                            if not user_stats['last_login'] or login_time > user_stats['last_login']:
                                user_stats['last_login'] = login_time
            
            return web.json_response(user_stats)
            
        except Exception as e:
            self.logger.error(f"获取用户统计失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_user_info(self, request):
        """获取单个用户详细信息"""
        try:
            player_name = request.match_info.get('player_name')
            if not player_name:
                return web.json_response({'error': '未提供玩家名称'}, status=400)
            
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                return web.json_response({'error': 'QQSync插件不可用'}, status=503)
            
            user_info = self.qqsync_interface.get_user_info(player_name)
            if not user_info:
                return web.json_response({'error': '用户不存在'}, status=404)
            
            return web.json_response({'user': user_info})
            
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_unbind_user(self, request):
        """解绑用户QQ"""
        try:
            player_name = request.match_info.get('player_name')
            if not player_name:
                return web.json_response({'error': '未提供玩家名称'}, status=400)
            
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                return web.json_response({'error': 'QQSync插件不可用'}, status=503)
            
            success = self.qqsync_interface.unbind_user(player_name, "WebUI管理员")
            
            if success:
                # 广播解绑事件
                await self._broadcast_user_event('unbind', {
                    'player_name': player_name,
                    'operator': 'WebUI管理员',
                    'timestamp': int(time.time())
                })
                
                return web.json_response({'success': True, 'message': f'用户 {player_name} 解绑成功'})
            else:
                return web.json_response({'success': False, 'error': '解绑失败'}, status=400)
                
        except Exception as e:
            self.logger.error(f"解绑用户失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_ban_user(self, request):
        """封禁用户"""
        try:
            player_name = request.match_info.get('player_name')
            if not player_name:
                return web.json_response({'error': '未提供玩家名称'}, status=400)
            
            data = await request.json()
            reason = data.get('reason', '')
            
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                return web.json_response({'error': 'QQSync插件不可用'}, status=503)
            
            success = self.qqsync_interface.ban_user(player_name, reason, "WebUI管理员")
            
            if success:
                # 广播封禁事件
                await self._broadcast_user_event('ban', {
                    'player_name': player_name,
                    'reason': reason,
                    'operator': 'WebUI管理员',
                    'timestamp': int(time.time())
                })
                
                return web.json_response({'success': True, 'message': f'用户 {player_name} 封禁成功'})
            else:
                return web.json_response({'success': False, 'error': '封禁失败'}, status=400)
                
        except Exception as e:
            self.logger.error(f"封禁用户失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_unban_user(self, request):
        """解封用户"""
        try:
            player_name = request.match_info.get('player_name')
            if not player_name:
                return web.json_response({'error': '未提供玩家名称'}, status=400)
            
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                return web.json_response({'error': 'QQSync插件不可用'}, status=503)
            
            success = self.qqsync_interface.unban_user(player_name, "WebUI管理员")
            
            if success:
                # 广播解封事件
                await self._broadcast_user_event('unban', {
                    'player_name': player_name,
                    'operator': 'WebUI管理员',
                    'timestamp': int(time.time())
                })
                
                return web.json_response({'success': True, 'message': f'用户 {player_name} 解封成功'})
            else:
                return web.json_response({'success': False, 'error': '解封失败'}, status=400)
                
        except Exception as e:
            self.logger.error(f"解封用户失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_restart_websocket(self, request):
        """重启WebSocket连接"""
        try:
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                return web.json_response({'success': False, 'message': 'QQSync插件不可用'})
            
            success = self.qqsync_interface.restart_websocket()
            
            if success:
                return web.json_response({'success': True, 'message': 'WebSocket重启中'})
            else:
                return web.json_response({'success': False, 'message': 'WebSocket重启失败'})
                
        except Exception as e:
            self.logger.error(f"重启WebSocket失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    def _get_uptime(self) -> str:
        """获取运行时间"""
        # 待实现
        return "运行中"
    
    def _get_message_count(self) -> int:
        """获取消息总数"""
        try:
            if self.qqsync_interface and self.qqsync_interface.is_available():
                statistics = self.qqsync_interface.get_statistics(30)
                return statistics.get('total_messages', 0)
            else:
                return 0
        except Exception as e:
            self.logger.error(f"获取消息总数失败: {e}")
            return 0
    
    async def api_unbind_user(self, request):
        """解绑用户QQ"""
        try:
            player_name = request.match_info['player_name']
            client_ip = request.remote
            
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                return web.json_response({'error': 'QQSync插件不可用'}, status=503)
            
            # 检查用户是否存在绑定
            user_info = self.qqsync_interface.get_user_info(player_name)
            if not user_info:
                return web.json_response({'error': '该玩家未绑定QQ'}, status=404)
            
            # 执行解绑操作
            success = self.qqsync_interface.unbind_user(player_name, f"WebUI({client_ip})")
            
            if success:
                self.logger.info(f"Web管理员解绑了玩家 {player_name} 的QQ (IP: {client_ip})")
                return web.json_response({'message': '解绑成功'})
            else:
                return web.json_response({'error': '解绑失败'}, status=500)
                
        except Exception as e:
            self.logger.error(f"解绑用户失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_statistics(self, request):
        """获取统计数据"""
        try:
            # 获取查询参数
            days = int(request.query.get('days', 30))
            
            if not self.qqsync_interface or not self.qqsync_interface.is_available():
                return web.json_response({
                    'error': 'QQSync插件不可用',
                    'data_stats': {},
                    'audit_stats': {},
                    'period_days': days
                }, status=503)
            
            # 获取统计数据
            stats = self.qqsync_interface.get_statistics(days)
            
            # 获取审计日志统计
            audit_logs = self.qqsync_interface.get_audit_logs(limit=1000, days=days)
            audit_stats = {
                'total_operations': len(audit_logs),
                'recent_operations': audit_logs[:10]  # 最近10条操作
            }
            
            result = {
                'data_stats': stats,
                'audit_stats': audit_stats,
                'period_days': days,
                'generated_at': datetime.now().isoformat()
            }
            
            return web.json_response(result)
            
        except Exception as e:
            self.logger.error(f"获取统计数据失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_get_message_stats(self, request):
        """API: 获取消息统计"""
        try:
            # 获取查询参数
            days = int(request.query.get('days', 7))
            
            # 获取统计数据
            stats = self._get_message_statistics(days)
            
            return web.json_response({
                'success': True,
                'data': stats,
                'period_days': days
            })
            
        except Exception as e:
            self.logger.error(f"获取消息统计失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def _get_status(self):
        """获取系统状态信息"""
        try:
            status = {
                'plugin_enabled': True,
                'websocket_connections': len(self.websocket_connections),
                'message_history_count': len(self.message_history),
                'qqsync_available': False,
                'server_info': {}
            }
            
            # 获取QQSync状态
            if self.qqsync_interface:
                status['qqsync_available'] = self.qqsync_interface.is_available()
                if status['qqsync_available']:
                    status['qqsync_status'] = self.qqsync_interface.get_connection_status()
                    status['server_info'] = self.qqsync_interface.get_server_info()
            
            return status
            
        except Exception as e:
            self.logger.error(f"获取状态失败: {e}")
            return {'error': str(e)}
    
    async def api_send_message(self, request):
        """API: 发送QQ消息"""
        try:
            data = await request.json()
            message = data.get('message', '').strip()
            
            if not message:
                return web.json_response({'error': '消息不能为空'}, status=400)
            
            if not self.qqsync_interface:
                return web.json_response({'error': 'QQSync接口不可用'}, status=500)
            
            success = self.qqsync_interface.send_message(message)

            msg = {
                    'timestamp': int(time.time()),
                    'sender': 'WebUI',
                    'content': message,
                    'type': 'chat',
                    'direction': 'webui_to_qq'
                }
            self._save_message_to_file(msg)
            
            result = {
                'success': success,
                'message': '消息发送成功' if success else '消息发送失败'
            }
            
            return web.json_response(result)
            
        except Exception as e:
            self.logger.error(f"发送消息API失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def api_send_game_message(self, request):
        """API: 发送消息到游戏服务器"""
        try:
            data = await request.json()
            message = data.get('message', '').strip()
            if not message:
                return web.json_response({'success': False, 'error': '消息不能为空'}, status=400)
            server = self.plugin.server
            if server:
                # 向所有在线玩家广播消息
                for player in server.online_players:
                    player.send_message(f"[WebUI] {message}")
                msg = {
                    'timestamp': int(time.time()),
                    'sender': 'WebUI',
                    'content': message,
                    'type': 'chat',
                    'direction': 'webui_to_game'
                }
                self._save_message_to_file(msg)
                return web.json_response({'success': True, 'message': '消息已发送到游戏'})
            else:
                return web.json_response({'success': False, 'error': '发送失败，服务器不可用'})
        except Exception as e:
            self.logger.error(f"发送游戏消息API失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def api_send_console_command(self, request):
        """API: 执行控制台命令"""
        try:
            data = await request.json()
            command = data.get('command', '').strip()
            if not command:
                return web.json_response({'success': False, 'error': '命令不能为空'}, status=400)
            server = self.plugin.server
            success = server.dispatch_command(server.command_sender, command)
            msg = {
                    'timestamp': int(time.time()),
                    'sender': 'WebUI',
                    'content': command,
                    'type': 'chat',
                    'direction': 'console'
                }
            self._save_message_to_file(msg)
            return web.json_response({'success': success})
        except Exception as e:
            self.logger.error(f"执行控制台命令API失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)
    
    def _save_message_to_file(self, message: dict):
        """保存消息到日期文件"""
        try:
            from datetime import datetime
            
            # 获取当前日期
            now = datetime.fromtimestamp(message['timestamp'])
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%H:%M:%S')
            
            # 构建文件路径
            file_path = self.message_storage_dir / f"{date_str}.txt"
            
            # 格式化消息
            direction_map = {
                'qq_to_game': '[QQ→游戏]',
                'game_to_qq': '[游戏→QQ]',
                'webui_to_game': '[WebUI→游戏]',
                'webui_to_qq': '[WebUI→QQ]',
                'console': '[控制台]',
                'unknown': '[未知]'
            }
            
            direction_str = direction_map.get(message['direction'], '[未知]')
            log_line = f"[{time_str}] {direction_str} {message['sender']}: {message['content']}\n"
            
            # 追加写入文件
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(log_line)
                
        except Exception as e:
            self.logger.error(f"保存消息到文件失败: {e}")

    def _get_recent_messages_from_file(self, limit: int = 50) -> list:
        """从消息文件读取最近N条历史消息"""
        from datetime import datetime, timedelta
        messages = []
        total_lines = 0
        parsed_lines = 0
        # 按日期倒序遍历最近7天的消息文件
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            file_path = self.message_storage_dir / f"{date}.txt"
            if not file_path.exists():
                continue
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                total_lines += len(lines)
                # 倒序读取
                for idx, line in enumerate(reversed(lines)):
                    try:
                        time_part, rest = line.split('] ', 1)
                        time_str = time_part.replace('[', '')
                        direction_part, rest2 = rest.split('] ', 1)
                        direction_str = direction_part.replace('[', '')
                        sender, content = rest2.split(': ', 1)
                        dt = datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M:%S")
                        messages.append({
                            'timestamp': int(dt.timestamp()),
                            'sender': sender.strip(),
                            'content': content.strip(),
                            'direction': direction_str
                        })
                        parsed_lines += 1
                        if len(messages) >= limit:
                            #self.logger.info(f"recent_messages: 解析成功 {parsed_lines}/{total_lines} 行，已达到限制 {limit}")
                            return messages
                    except Exception as e:
                        self.logger.warning(f"recent_messages: 解析失败 行[{idx}] 内容: {line.strip()} 错误: {e}")
                        continue
        #self.logger.info(f"recent_messages: 解析成功 {parsed_lines}/{total_lines} 行，返回 {len(messages)} 条消息")
        return messages
    
    def _get_message_statistics(self, days: int = 7) -> dict:
        """从文件中获取消息统计"""
        try:
            from datetime import datetime, timedelta
            
            stats = {
                'total_messages': 0,
                'daily_stats': {},
                'direction_stats': {
                    'qq_to_game': 0,
                    'game_to_qq': 0,
                    'webui_to_game': 0,
                    'console': 0,
                    'unknown': 0
                },
                'hourly_stats': {}  # 24小时统计
            }
            
            # 初始化小时统计
            for hour in range(24):
                stats['hourly_stats'][f"{hour:02d}"] = 0
            
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days-1)
            
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                file_path = self.message_storage_dir / f"{date_str}.txt"
                
                daily_count = 0
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        daily_count = len(lines)
                        
                        # 分析每行消息
                        for line in lines:
                            stats['total_messages'] += 1
                            
                            # 提取时间和方向
                            if '[' in line and ']' in line:
                                try:
                                    # 提取时间 [HH:MM:SS]
                                    time_match = line.split(']')[0].replace('[', '')
                                    if ':' in time_match:
                                        hour = int(time_match.split(':')[0])
                                        stats['hourly_stats'][f"{hour:02d}"] += 1
                                    
                                    # 提取方向
                                    if '[QQ→游戏]' in line:
                                        stats['direction_stats']['qq_to_game'] += 1
                                    elif '[游戏→QQ]' in line:
                                        stats['direction_stats']['game_to_qq'] += 1
                                    elif '[WebUI→游戏]' in line:
                                        stats['direction_stats']['webui_to_game'] += 1
                                    elif '[控制台]' in line:
                                        stats['direction_stats']['console'] += 1
                                    else:
                                        stats['direction_stats']['unknown'] += 1
                                        
                                except:
                                    pass
                
                stats['daily_stats'][date_str] = daily_count
                current_date += timedelta(days=1)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取消息统计失败: {e}")
            return {
                'total_messages': 0,
                'daily_stats': {},
                'direction_stats': {},
                'hourly_stats': {}
            }
            return False, error_msg
            
        except Exception as e:
            self.logger.error(f"获取审计日志失败: {e}")
            return web.json_response({'error': str(e)}, status=500)