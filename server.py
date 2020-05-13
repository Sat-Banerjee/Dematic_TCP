import util
import time
import traceback
from threading import Thread
import RxThread
import DematicMsgHandler
from queue import Queue
import sys
import enum

# --------------------------------------------------------

class ServerUserOpts(enum.IntEnum):
    System_Armed = 1,
    System_UnArmed = 2,
    PLC_Status = 3,
    Exit_App = 20


def print_and_get_user_inp(opts):
    user_inp = -1

    for msg in sorted(opts):
        print ("\t {:2} : {}".format(str(msg.value), str(msg.name)))

    try:
        user_inp = int(input ("\t Enter your Choice: "))
    except Exception as e:
        pass

    return user_inp

# ------------------------------------------------------------
def handle_user_inp(opts, user_inp, dematicHandler):
    retval = 0

    if (user_inp == -1):
        pass

    elif (user_inp == opts.Exit_App):
        retval = -1

    else:
        dematicHandler.processUserInp(user_inp)

    return retval

# ------------------------------------------------------------
# command line args
if (len(sys.argv) != 3):
    print ("Invalid no. of command line args. Usage python {} <ip> <port>".format(sys.argv[0]))
    exit(-1)

ip = str(sys.argv[1])
port = int(sys.argv[2])

print ("------------------------------------------------------")
print ("Dummy DEMATIC PLC")
print ("------------------------------------------------------")


keep_alive_time = 15   # secs
myLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./server_log.txt")
myLogger.log("\n----------------- NEW SESSION -----------------")
myServer = util.SockUtil(util.CONFIG.SERVER, logger=myLogger)

myServer.create_socket()
myServer.bind(ip, port)

data = None
dataLen = 0

ctr = 1

try:
    # user opts
    userOpts = ServerUserOpts

    # create the Q for threads to communicate
    threadQ = Queue(maxsize=0)      # infinite size

    # Dematic Message Handler Obj
    dematicMsgHandlerObj = DematicMsgHandler.DematicMsgHandler(qName=threadQ,
                                                                userOptsEnum=userOpts,
                                                                sockObj=myServer,
                                                                logger=myLogger,
                                                                keepAliveTime=keep_alive_time,
                                                                threadName="DematicMsgHandler")

    # timer
    dematicMsgHandlerObj.startTimer()

    # create the Rx thread obj
    rxThreadObj = RxThread.RxThread(qName=threadQ, 
                                    sockObj=myServer, 
                                    logger=myLogger,
                                    decodeFn=dematicMsgHandlerObj.process_Rx_Message, 
                                    threadName="RxThread")

    # start the server, for incoming connections
    myServer.start_server()

    # start the rx thread 
    rxThreadObj.start()

    while(not rxThreadObj.stop_thread):
        user_inp = print_and_get_user_inp(userOpts)
        if (handle_user_inp(userOpts, user_inp, dematicHandler=dematicMsgHandlerObj) == -1):
            break


except Exception as e:
    myLogger.log_exception(e, traceback)
    rxThreadObj.stop_thread = True


# wait for rx thread to join
rxThreadObj.stop_thread = True
dematicMsgHandlerObj.cancelTimer()
rxThreadObj.join(2.0)   # join timeout

myServer.close()
myLogger.log("Exiting Server.py")
myLogger.closeLogger()



