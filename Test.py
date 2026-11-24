from ib_async import IB

ib = IB()

ib.connect("127.0.0.1", 4002, clientId = 1, timeout = 10)

print("connected:", ib.isConnected())
print("server time:", ib.reqCurrentTime())
print("account:", ib.managedAccounts())

ib.disconnect()