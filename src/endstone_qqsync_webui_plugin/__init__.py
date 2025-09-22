"""
QQSync WebUI 插件模块
为 endstone-qqsync-plugin 提供 Web 管理界面
"""

# 直接从lib目录导入依赖
import sys
from pathlib import Path

# 添加lib路径到sys.path
lib_path = Path(__file__).parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

# 导入主要组件
try:
    from .qqsync_webui_plugin import qqsyncwebui
    from .server import WebUIServer
    from .config import WebUIConfigManager
    from .api import QQSyncInterface
    WEBUI_AVAILABLE = True
except ImportError as e:
    print(f"QQSync WebUI插件导入失败: {e}")
    QQSyncWebUIPlugin = None
    WebUIServer = None
    WebUIConfigManager = None
    QQSyncInterface = None
    WEBUI_AVAILABLE = False

__all__ = [
    "qqsyncwebui",
    "WebUIServer", 
    "WebUIConfigManager",
    "QQSyncInterface",
    "WEBUI_AVAILABLE"
]