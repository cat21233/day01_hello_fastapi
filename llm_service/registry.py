"""工具实现层：模型叫的名字 → 真正的 Python 函数"""
import time


def get_weather(city: str) -> str:
    """查询指定城市的天气。参数 city 是城市名。"""
    return f"{city}：晴，28℃，微风"


def get_time(city: str) -> str:
    """查询指定城市的当前时间。参数 city 是城市名。"""
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"{city} 的当前时间是 {now}"