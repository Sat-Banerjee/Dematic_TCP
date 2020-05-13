import util
import time
import traceback

myLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./server_log.txt")
myServer = util.SockUtil(util.CONFIG.SERVER, logger=myLogger)

myServer.create_socket()
myServer.bind("localhost", 45000)

myServer.start_server()

data = None
dataLen = 0

ctr = 0

try:
    while(True):
        data, dataLen = myServer.receive_data(expected_data_len=4)
        if data is not None:
            myLogger.log("server: data received {} bytes: {}".format(str(dataLen), data))
            data = data + "_" + str(ctr)
            ctr += 2
            myServer.send_data(data)
        time.sleep(1)   # 1s
except Exception as e:
    myLogger.log_exception(e, traceback)

finally:
    myServer.close()
    myLogger.log("Exiting Server.py")
    myLogger.closeLogger()
    

