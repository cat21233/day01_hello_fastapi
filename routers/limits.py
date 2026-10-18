"""全局限流器：限制同一个 IP 在单位时间内的请求次数。

用于防止接口被人恶意刷、被脚本高频爬取，或异常重试把服务打垮。
基于 slowapi，以客户端 IP 作为限流键，超过阈值直接返回 429。
"""

"""全局限流器：限制同一个 IP 在单位时间内的请求次数。

用于防止接口被人恶意刷、被脚本高频爬取，或异常重试把服务打垮。
基于 slowapi，以客户端 IP 作为限流键，超过阈值直接返回 429。
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
