import os
import sys

from ib_async import IB

from engine import IB_CLIENT_ID, IB_HOST, IB_PORT

# 使用不同的 clientId，避免与正在运行的 engine 冲突
client_id = int(os.getenv('HEALTHCHECK_CLIENT_ID', IB_CLIENT_ID + 100))

ib = IB()
try:
    ib.connect(IB_HOST, IB_PORT, clientId=client_id, timeout=10)
    print("连接成功：", ib.isConnected(), "| 账户：", ib.managedAccounts(), "| 服务器时间：", ib.reqCurrentTime())
except Exception as e:
    print("连接失败：", e)
    sys.exit(1)
finally:
    ib.disconnect()
