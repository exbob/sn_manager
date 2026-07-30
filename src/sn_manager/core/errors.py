class SnError(Exception):
    """SN 管理核心层异常基类。"""


class ValidationError(SnError):
    """字段或 SN 格式校验失败。"""


class SequenceExhaustedError(SnError):
    """同维度序号已用尽。"""

    def __init__(self) -> None:
        super().__init__("序号已用尽，请更换生产日期或硬件批次")
