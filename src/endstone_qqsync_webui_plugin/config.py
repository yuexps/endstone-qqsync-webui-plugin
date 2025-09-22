"""
WebUI配置管理模块
管理WebUI插件的服务器配置
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any


class WebUIConfigManager:
    """WebUI配置管理器"""
    
    def __init__(self, data_folder: Path):
        self.data_folder = data_folder
        self.config_file = data_folder / "webui_config.json"
        self.logger = logging.getLogger("WebUIConfig")
        # 默认配置
        self.default_config = {
            "server": {
                "host": "127.0.0.1",
                "port": 8080,
            }
        }
        self.config = {}
        # 如果配置文件不存在，则写入默认配置
        if not self.config_file.exists():
            self.config = self.default_config.copy()
            self.save_config()
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                self.config.update(loaded_config)
                self.logger.info("配置已加载")
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
    
    def save_config(self):
        """保存配置到文件"""
        try:
            self.data_folder.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.logger.info("配置已保存")
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
    
    def get_config(self, key: str, default=None):
        """获取配置值（支持点号分隔的路径）"""
        try:
            keys = key.split('.')
            value = self.config
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            
            return value
            
        except Exception:
            return default
    
    def set_config(self, key: str, value: Any):
        """设置配置值（支持点号分隔的路径）"""
        try:
            keys = key.split('.')
            config = self.config
            
            # 导航到最后一级的父级
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            # 设置值
            config[keys[-1]] = value
            
        except Exception as e:
            self.logger.error(f"设置配置失败 {key}={value}: {e}")
    
    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.config.copy()
    
    def update_config(self, updates: Dict[str, Any]):
        """批量更新配置"""
        try:
            for key, value in updates.items():
                self.set_config(key, value)
            
            self.save_config()
            
        except Exception as e:
            self.logger.error(f"批量更新配置失败: {e}")
    
    def validate_config(self) -> list:
        """验证配置的有效性，返回错误列表"""
        errors = []
        
        try:
            # 验证服务器配置
            server_config = self.get_config('server', {})
            
            port = server_config.get('port', 8080)
            if not isinstance(port, int) or port < 1 or port > 65535:
                errors.append("server.port 必须是1-65535之间的整数")
            
            host = server_config.get('host', '127.0.0.1')
            if not isinstance(host, str) or not host:
                errors.append("server.host 必须是有效的主机地址")
            
        except Exception as e:
            errors.append(f"配置验证时发生错误: {str(e)}")
        
        return errors