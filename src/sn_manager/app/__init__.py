"""应用服务层。"""

from sn_manager.app.paths import (
    default_db_path,
    resolve_app_icon_path,
    resolve_user_manual_path,
)
from sn_manager.app.services import MasterSnapshot, SnService
from sn_manager.app.version import resolve_app_version

__all__ = [
    "MasterSnapshot",
    "SnService",
    "default_db_path",
    "resolve_app_icon_path",
    "resolve_app_version",
    "resolve_user_manual_path",
]
