class SnError(Exception):
    """SN 管理核心层异常基类。"""


class ValidationError(SnError):
    """字段或 SN 格式校验失败。"""
