from .base import BaseLottery
from .ssq import SSQLottery
from .dlt import DLTLottery
from .digital import FC3DLottery, PL3Lottery, PL5Lottery, QXCLottery


def get_lottery(lottery_type: str) -> BaseLottery:
    """工厂方法：根据彩种类型获取实例"""
    registry = {
        "ssq": SSQLottery,
        "dlt": DLTLottery,
        "fc3d": FC3DLottery,
        "pl3": PL3Lottery,
        "pl5": PL5Lottery,
        "qxc": QXCLottery,
    }
    cls = registry.get(lottery_type)
    if not cls:
        raise ValueError(f"不支持的彩种: {lottery_type}")
    return cls()


def get_all_lottery_types():
    """获取所有支持的彩种类型"""
    return ["ssq", "dlt", "fc3d", "pl3", "pl5", "qxc"]


__all__ = [
    "BaseLottery", "SSQLottery", "DLTLottery",
    "FC3DLottery", "PL3Lottery", "PL5Lottery", "QXCLottery",
    "get_lottery", "get_all_lottery_types"
]
