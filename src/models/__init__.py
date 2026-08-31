from .base import BaseLottery
from .ssq import SSQLottery
from .dlt import DLTLottery


def get_lottery(lottery_type: str) -> BaseLottery:
    """工厂方法：根据彩种类型获取实例"""
    registry = {
        "ssq": SSQLottery,
        "dlt": DLTLottery,
    }
    cls = registry.get(lottery_type)
    if not cls:
        raise ValueError(f"不支持的彩种: {lottery_type}")
    return cls()


__all__ = ["BaseLottery", "SSQLottery", "DLTLottery", "get_lottery"]
