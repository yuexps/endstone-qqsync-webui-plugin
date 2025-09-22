"""
QQSync插件接口模块
提供与主QQSync插件的接口，通过plugin_manager获取插件实例
"""

import json
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


class QQSyncInterface:
    """QQSync插件接口"""
    
    def __init__(self, plugin_manager):
        self.plugin_manager = plugin_manager
        self.logger = logging.getLogger("QQSyncInterface")
        self._qqsync_plugin = None
        self._last_check_time = 0
        self._check_interval = 5  # 5秒检查一次
    
    def _get_qqsync_plugin(self):
        """获取QQSync插件实例"""
        import time
        current_time = time.time()
        
        # 缓存检查，避免频繁调用
        if current_time - self._last_check_time < self._check_interval and self._qqsync_plugin:
            return self._qqsync_plugin
        
        try:
            self._qqsync_plugin = self.plugin_manager.get_plugin('qqsync_plugin')
            self._last_check_time = current_time
            
            if not self._qqsync_plugin:
                self.logger.warning("QQSync插件未找到或未启用")
                
            return self._qqsync_plugin
            
        except Exception as e:
            self.logger.error(f"获取QQSync插件失败: {e}")
            return None
    
    def is_available(self) -> bool:
        """检查QQSync插件是否可用"""
        plugin = self._get_qqsync_plugin()
        return plugin is not None
    
    def get_plugin_info(self) -> Dict[str, Any]:
        """获取插件基本信息"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return {
                'available': False,
                'error': 'QQSync插件未找到'
            }
        
        try:
            # 获取插件是否启用状态
            is_enabled = getattr(plugin, 'is_enabled', True)
            if callable(is_enabled):
                enabled_status = is_enabled()
            else:
                enabled_status = bool(is_enabled)
            
            return {
                'available': True,
                'name': getattr(plugin, 'name', 'qqsync_plugin'),
                'version': getattr(plugin, 'version', 'unknown'),
                'enabled': enabled_status,
                'description': getattr(plugin, 'description', 'QQSync群服互通插件')
            }
        except Exception as e:
            self.logger.error(f"获取插件信息失败: {e}")
            return {
                'available': True,
                'error': str(e)
            }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return {
                'websocket_connected': False,
                'bot_online': False,
                'last_ping': None,
                'error': 'QQSync插件不可用'
            }
        
        try:
            # 获取WebSocket连接状态
            ws_connected = False
            bot_online = False
            last_ping = None
            
            if hasattr(plugin, 'ws_client'):
                ws_connected = getattr(plugin.ws_client, 'is_connected', False)
                if callable(ws_connected):
                    ws_connected = ws_connected()
                
                last_ping = getattr(plugin.ws_client, 'last_ping', None)
            
            # 检查机器人在线状态
            if hasattr(plugin, 'bot_online'):
                bot_online = plugin.bot_online
            elif hasattr(plugin, 'is_bot_online'):
                bot_online = plugin.is_bot_online()
            
            return {
                'websocket_connected': ws_connected,
                'bot_online': bot_online,
                'last_ping': last_ping,
                'reconnect_attempts': getattr(plugin, '_reconnect_attempts', 0)
            }
            
        except Exception as e:
            self.logger.error(f"获取连接状态失败: {e}")
            return {
                'websocket_connected': False,
                'bot_online': False,
                'last_ping': None,
                'error': str(e)
            }
    
    def get_config(self, key: str = None) -> Dict[str, Any]:
        """获取QQSync插件配置"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return {}
        
        try:
            if hasattr(plugin, 'config_manager'):
                if key:
                    return {key: plugin.config_manager.get_config(key)}
                else:
                    # 获取主要配置项
                    config_keys = [
                        'napcat_ws', 'access_token', 'target_group', 'admins',
                        'enable_qq_to_game', 'enable_game_to_qq', 'force_bind_qq',
                        'sync_group_card', 'check_group_member', 'chat_count_limit',
                        'chat_ban_time', 'api_qq_enable'
                    ]
                    
                    config = {}
                    for k in config_keys:
                        config[k] = plugin.config_manager.get_config(k)
                    
                    return config
            else:
                return {}
                
        except Exception as e:
            self.logger.error(f"获取配置失败: {e}")
            return {'error': str(e)}
    
    def set_config(self, key: str, value: Any) -> bool:
        """设置QQSync插件配置"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            self.logger.error("QQSync插件不可用，无法设置配置")
            return False
        
        try:
            if hasattr(plugin, 'config_manager'):
                # 设置配置值
                plugin.config_manager.set_config(key, value)
                
                # 保存配置
                if hasattr(plugin.config_manager, 'save_config'):
                    plugin.config_manager.save_config()
                elif hasattr(plugin.config_manager, 'save'):
                    plugin.config_manager.save()
                
                self.logger.info(f"已更新QQSync配置: {key} = {value}")
                return True
            else:
                self.logger.error("QQSync插件没有config_manager属性")
                return False
                
        except Exception as e:
            self.logger.error(f"设置QQSync配置失败 {key}={value}: {e}")
            return False
    
    def update_config(self, config_updates: Dict[str, Any]) -> Dict[str, bool]:
        """批量更新QQSync插件配置"""
        plugin = self._get_qqsync_plugin()
        results = {}
        
        if not plugin:
            self.logger.error("QQSync插件不可用，无法更新配置")
            return {key: False for key in config_updates.keys()}
        
        try:
            if hasattr(plugin, 'config_manager'):
                # 批量设置配置
                for key, value in config_updates.items():
                    try:
                        plugin.config_manager.set_config(key, value)
                        results[key] = True
                        self.logger.debug(f"已设置QQSync配置: {key} = {value}")
                    except Exception as e:
                        self.logger.error(f"设置QQSync配置失败 {key}={value}: {e}")
                        results[key] = False
                
                # 统一保存配置
                try:
                    if hasattr(plugin.config_manager, 'save_config'):
                        plugin.config_manager.save_config()
                    elif hasattr(plugin.config_manager, 'save'):
                        plugin.config_manager.save()
                    
                    self.logger.info(f"QQSync配置已保存，更新项: {list(config_updates.keys())}")
                except Exception as e:
                    self.logger.error(f"保存QQSync配置失败: {e}")
                    # 如果保存失败，将所有结果标记为失败
                    for key in results:
                        results[key] = False
                
            else:
                self.logger.error("QQSync插件没有config_manager属性")
                results = {key: False for key in config_updates.keys()}
                
        except Exception as e:
            self.logger.error(f"批量更新QQSync配置失败: {e}")
            results = {key: False for key in config_updates.keys()}
        
        return results
    
    def get_users(self) -> List[Dict[str, Any]]:
        """获取用户绑定信息"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return []
        
        try:
            if hasattr(plugin, 'data_manager'):
                # 直接访问_binding_data属性
                bindings = getattr(plugin.data_manager, '_binding_data', {})
                
                if not isinstance(bindings, dict):
                    self.logger.warning("绑定数据格式异常")
                    return []
                
                users = []
                
                # 获取在线玩家列表用于检查在线状态
                online_players = []
                if hasattr(plugin, 'server') and plugin.server:
                    online_players = [p.name for p in plugin.server.online_players]
                
                for player_name, user_data in bindings.items():
                    if not isinstance(user_data, dict):
                        continue
                    
                    # 直接使用QQSync的数据结构，不需要额外的API调用
                    user_info = {
                        'player_name': player_name,
                        'name': user_data.get('name', player_name),
                        'qq_number': user_data.get('qq', ''),
                        'xuid': user_data.get('xuid', ''),
                        'is_online': player_name in online_players,
                        
                        # 绑定相关时间
                        'bind_time': user_data.get('bind_time'),
                        'unbind_time': user_data.get('unbind_time'),
                        'rebind_time': user_data.get('rebind_time'),
                        'unbind_by': user_data.get('unbind_by', ''),
                        'unbind_reason': user_data.get('unbind_reason', ''),
                        'original_qq': user_data.get('original_qq', ''),
                        
                        # 游戏统计数据
                        'total_playtime': user_data.get('total_playtime', 0),
                        'session_count': user_data.get('session_count', 0),
                        'last_join_time': user_data.get('last_join_time'),
                        'last_quit_time': user_data.get('last_quit_time'),
                        
                        # 封禁相关
                        'is_banned': user_data.get('is_banned', False),
                        'ban_time': user_data.get('ban_time'),
                        'ban_by': user_data.get('ban_by', ''),
                        'ban_reason': user_data.get('ban_reason', ''),
                        'unban_time': user_data.get('unban_time'),
                        'unban_by': user_data.get('unban_by', ''),
                        
                        # 绑定状态判断
                        'is_bound': bool(user_data.get('qq', '').strip())
                    }
                    
                    # 计算绑定状态描述
                    if user_info['is_bound']:
                        if user_info['rebind_time']:
                            user_info['binding_status'] = '重新绑定'
                        else:
                            user_info['binding_status'] = '已绑定'
                    else:
                        if user_info['unbind_time']:
                            user_info['binding_status'] = '已解绑'
                        elif user_info['original_qq']:
                            user_info['binding_status'] = '历史绑定'
                        else:
                            user_info['binding_status'] = '从未绑定'
                    
                    users.append(user_info)
                
                return users
            else:
                self.logger.warning("QQSync插件没有data_manager属性")
                return []
                
        except Exception as e:
            self.logger.error(f"获取用户列表失败: {e}")
            return []
    
    def get_user_info(self, player_name: str) -> Optional[Dict[str, Any]]:
        """获取单个用户信息"""
        users = self.get_users()
        for user in users:
            if user['player_name'] == player_name:
                return user
        return None
    
    def unbind_user(self, player_name: str, operator: str = "WebUI") -> bool:
        """解绑用户QQ"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return False
        
        try:
            if hasattr(plugin, 'data_manager') and hasattr(plugin.data_manager, 'unbind_player_qq'):
                # 使用QQSync插件的unbind_player_qq方法
                result = plugin.data_manager.unbind_player_qq(player_name, operator)
                if result:
                    self.logger.info(f"用户 {player_name} 的QQ绑定已解除（操作者：{operator}）")
                return result
            else:
                self.logger.warning("QQSync插件没有unbind_player_qq方法")
                return False
                
        except Exception as e:
            self.logger.error(f"解绑用户失败: {e}")
            return False
    
    def ban_user(self, player_name: str, reason: str = "", operator: str = "WebUI") -> bool:
        """封禁用户"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return False
        
        try:
            if hasattr(plugin, 'data_manager') and hasattr(plugin.data_manager, 'ban_player'):
                # 使用QQSync插件的ban_player方法
                result = plugin.data_manager.ban_player(player_name, operator, reason)
                if result:
                    self.logger.info(f"用户 {player_name} 已被封禁（操作者：{operator}，原因：{reason}）")
                return result
            else:
                self.logger.warning("QQSync插件没有ban_player方法")
                return False
                
        except Exception as e:
            self.logger.error(f"封禁用户失败: {e}")
            return False
    
    def unban_user(self, player_name: str, operator: str = "WebUI") -> bool:
        """解封用户"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return False
        
        try:
            if hasattr(plugin, 'data_manager') and hasattr(plugin.data_manager, 'unban_player'):
                # 使用QQSync插件的unban_player方法
                result = plugin.data_manager.unban_player(player_name, operator)
                if result:
                    self.logger.info(f"用户 {player_name} 已被解封（操作者：{operator}）")
                return result
            else:
                self.logger.warning("QQSync插件没有unban_player方法")
                return False
                
        except Exception as e:
            self.logger.error(f"解封用户失败: {e}")
            return False
    
    def send_message(self, message: str) -> bool:
        """发送消息到QQ群"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return False
        
        try:
            # 使用QQSync插件的api_send_message方法
            if hasattr(plugin, 'api_send_message'):
                success = plugin.api_send_message(f"[WebUI] {message}")
                if success:
                    self.logger.info("✅ 消息发送成功")
                else:
                    self.logger.info("❌ 消息发送失败")
                return success
            else:
                self.logger.warning("QQSync插件没有api_send_message方法")
                return False
                
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
            return False
    
    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """获取统计数据"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return {}
        
        try:
            if hasattr(plugin, 'data_manager'):
                # QQSync插件没有统计方法，我们手动计算
                bindings = getattr(plugin.data_manager, '_binding_data', {})
                
                if not isinstance(bindings, dict):
                    return {}
                
                # 获取在线玩家列表
                online_players = []
                if hasattr(plugin, 'server') and plugin.server:
                    online_players = [p.name for p in plugin.server.online_players]
                
                # 计算基本统计
                total_users = len(bindings)
                bound_users = sum(1 for data in bindings.values() if data.get('qq', '').strip())
                online_users = sum(1 for name in bindings.keys() if name in online_players)
                banned_users = sum(1 for data in bindings.values() if data.get('is_banned', False))
                
                # 计算总游戏时间
                total_playtime = sum(data.get('total_playtime', 0) for data in bindings.values())
                
                # 计算总会话数
                total_sessions = sum(data.get('session_count', 0) for data in bindings.values())
                
                stats = {
                    'total_users': total_users,
                    'bound_users': bound_users,
                    'unbound_users': total_users - bound_users,
                    'online_users': online_users,
                    'offline_users': total_users - online_users,
                    'banned_users': banned_users,
                    'total_playtime': total_playtime,
                    'total_sessions': total_sessions,
                    'average_playtime': total_playtime / total_users if total_users > 0 else 0,
                    'average_sessions': total_sessions / total_users if total_users > 0 else 0
                }
                
                return stats
            else:
                return {}
                
        except Exception as e:
            self.logger.error(f"获取统计数据失败: {e}")
            return {'error': str(e)}
    
    def get_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近消息"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return []
        
        try:
            # 检查是否有消息存储目录
            if hasattr(plugin, 'message_storage_dir'):
                import os
                from pathlib import Path
                from datetime import datetime
                
                storage_dir = Path(plugin.message_storage_dir)
                if not storage_dir.exists():
                    return []
                
                # 获取所有消息文件，按日期排序
                message_files = []
                for file_path in storage_dir.glob('*.txt'):
                    if file_path.is_file():
                        try:
                            # 从文件名提取日期
                            date_str = file_path.stem
                            datetime.strptime(date_str, '%Y-%m-%d')
                            message_files.append((file_path, date_str))
                        except ValueError:
                            continue
                
                if not message_files:
                    return []
                
                # 按日期排序，最新的在前
                message_files.sort(key=lambda x: x[1], reverse=True)
                
                messages = []
                files_to_read = message_files[:3]  # 读取最近3天的文件
                
                # 解析消息的正则表达式
                import re
                message_pattern = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\]\s*\[([^\]]+)\]\s*([^:]+):\s*(.+)$')
                
                for file_path, date_str in files_to_read:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        
                        for line in reversed(lines):  # 从最新的消息开始读取
                            line = line.strip()
                            if not line:
                                continue
                            
                            match = message_pattern.match(line)
                            if match:
                                time_str, direction_str, sender, content = match.groups()
                                
                                # 构建完整时间戳
                                timestamp_str = f"{date_str} {time_str}"
                                try:
                                    timestamp = int(datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').timestamp())
                                except ValueError:
                                    continue
                                
                                # 解析方向
                                direction_map = {
                                    'QQ→游戏': 'qq_to_game',
                                    '游戏→QQ': 'game_to_qq', 
                                    'WebUI→游戏': 'webui_to_game',
                                    'WebUI→QQ': 'webui_to_qq',
                                    '控制台': 'console'
                                }
                                
                                direction = direction_map.get(direction_str.replace('[', '').replace(']', ''), 'unknown')
                                
                                # 确定消息类型
                                if direction == 'console':
                                    message_type = 'system'
                                elif sender.lower() in ['system', '控制台', 'console']:
                                    message_type = 'system'
                                else:
                                    message_type = 'chat'
                                
                                messages.append({
                                    'timestamp': timestamp,
                                    'sender': sender,
                                    'content': content,
                                    'message_type': message_type,
                                    'direction': direction
                                })
                                
                                if len(messages) >= limit:
                                    break
                            
                            if len(messages) >= limit:
                                break
                        
                        if len(messages) >= limit:
                            break
                            
                    except Exception as e:
                        self.logger.error(f"读取消息文件 {file_path} 失败: {e}")
                        continue
                
                # 按时间戳排序，最新的在前
                messages.sort(key=lambda x: x['timestamp'], reverse=True)
                return messages[:limit]
            
            else:
                # 如果没有消息存储功能，返回默认消息
                return [
                    {
                        'timestamp': int(time.time()),
                        'sender': 'System',
                        'content': '消息历史功能暂未启用',
                        'message_type': 'system',
                        'direction': 'system'
                    }
                ]
                
        except Exception as e:
            self.logger.error(f"获取最近消息失败: {e}")
            return []
    
    def get_audit_logs(self, limit: int = 100, action_type: str = '', 
                      operator: str = '', days: int = 30) -> List[Dict[str, Any]]:
        """获取审计日志"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return []
        
        try:
            if hasattr(plugin, 'data_manager') and hasattr(plugin.data_manager, 'audit_logger'):
                return plugin.data_manager.audit_logger.get_logs(
                    limit=limit,
                    action_type=action_type,
                    operator=operator,
                    days=days
                )
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"获取审计日志失败: {e}")
            return []
    
    def restart_websocket(self) -> bool:
        """重启WebSocket连接"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return False
        
        try:
            if hasattr(plugin, 'ws_client'):
                # 停止现有连接
                if hasattr(plugin.ws_client, 'stop'):
                    plugin.ws_client.stop()
                
                # 重新连接
                if hasattr(plugin.ws_client, 'connect_forever'):
                    import asyncio
                    if hasattr(plugin, '_loop'):
                        future = asyncio.run_coroutine_threadsafe(
                            plugin.ws_client.connect_forever(),
                            plugin._loop
                        )
                        return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"重启WebSocket失败: {e}")
            return False
    
    def execute_command(self, command: str, operator: str = "WebUI") -> Dict[str, Any]:
        """执行服务器命令（如果支持）"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return {'success': False, 'error': 'QQSync插件不可用'}
        
        try:
            # 检查是否有命令执行功能
            if hasattr(plugin, 'execute_server_command'):
                result = plugin.execute_server_command(command)
                
                # 记录操作日志
                if hasattr(plugin, 'data_manager') and hasattr(plugin.data_manager, 'audit_logger'):
                    plugin.data_manager.audit_logger.log_admin_action(
                        action="command_execute",
                        operator=operator,
                        target=command,
                        details={'command': command, 'method': 'webui'}
                    )
                
                return {'success': True, 'result': result}
            else:
                return {'success': False, 'error': '插件不支持命令执行'}
                
        except Exception as e:
            self.logger.error(f"执行命令失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        plugin = self._get_qqsync_plugin()
        if not plugin:
            return {}
        
        try:
            info = {}
            
            if hasattr(plugin, 'server') and plugin.server:
                server = plugin.server
                info.update({
                    'online_players_count': len(server.online_players),
                    'online_players': [p.name for p in server.online_players],
                    'server_name': getattr(server, 'name', 'Unknown'),
                    'max_players': getattr(server, 'max_players', 0),
                })
            
            # 添加插件特定信息
            info.update({
                'bound_users_count': len(self.get_users()),
                'connection_status': self.get_connection_status(),
                'plugin_info': self.get_plugin_info()
            })
            
            return info
            
        except Exception as e:
            self.logger.error(f"获取服务器信息失败: {e}")
            return {'error': str(e)}