import util
import time
import traceback
from threading import Thread
import RxThread
import DematicMsgHandler
from multiprocessing import Queue
import sys
import enum

# --------------------------------------------------------

class ServerUserOpts(enum.IntEnum):
    System_Armed = 1,
    System_UnArmed = 2,
    Peripheral_Emergency_Active = 3,
    Peripheral_Emergency_Resolved = 4,
    PLC_Status_Response = 5,
    Exit_App = 20


def print_and_get_user_inp(opts):
    user_inp = -1

    for msg in sorted(opts):
        print ("\t {:2} : {}".format(str(msg.value), str(msg.name)))

    try:
        user_inp = int(input ("\t Enter your Choice: "))
    except KeyboardInterrupt as e:
        user_inp = 20
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
if (len(sys.argv) < 3):
    print ("Invalid no. of command line args. Usage python {} <ip> <port> <o: loop-time> <o: retry>".format(sys.argv[0]))
    exit(-1)

ip = str(sys.argv[1])
port = int(sys.argv[2])
loopTime = None
connectionRetry = False

keep_alive_time = 6   # secs
fileCreationTime = util.getFormattedTimeStamp()
myLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./server_log_" + fileCreationTime + ".txt")
myTimeLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./server_life_rx_log_" + fileCreationTime + ".txt")
myAckLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./server_ack_rx_log_" + fileCreationTime + ".csv")

print ("------------------------------------------------------")
if (len(sys.argv) >= 4):
    loopTime = float(sys.argv[3])
    print ("Dummy DEMATIC PLC (Automated for Sending)")
    myLogger.log("\n----------------- NEW SESSION (Automated for Sending) -----------------")
else:
    print ("Dummy DEMATIC PLC with User Options)")
    myLogger.log("\n----------------- NEW SESSION -----------------")
print ("------------------------------------------------------")

try:
    connectionRetry = bool (sys.argv[4])
except Exception as e:
    pass

myLogger.log ("Connection Retry: {}".format(str(connectionRetry)))

myServer = util.SockUtil(util.CONFIG.SERVER, logger=myLogger, retry=connectionRetry)

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
                                                                threadName="DematicMsgHandler",
                                                                ackLogger=myAckLogger,
                                                                timeLogger=myTimeLogger,
                                                                seq_start_from=10000000,    # star the seq.no generation from this
                                                                validateMessage=True)

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

    # timer
    dematicMsgHandlerObj.startTimer()

    while(not rxThreadObj.stop_thread):
        try:
            if loopTime is not None:
                dematicMsgHandlerObj.processUserInp(1)
                time.sleep (loopTime)
                dematicMsgHandlerObj.processUserInp(2)
                time.sleep (loopTime)
                dematicMsgHandlerObj.processUserInp(3)
                time.sleep (loopTime)
                dematicMsgHandlerObj.processUserInp(4)
                time.sleep (loopTime)
                dematicMsgHandlerObj.processUserInp(5)
                time.sleep (loopTime)
            else:
                user_inp = print_and_get_user_inp(userOpts)
                if (handle_user_inp(userOpts, user_inp, dematicHandler=dematicMsgHandlerObj) == -1):
                    break
        except KeyboardInterrupt as e:
            break
        except Exception as e:
            break

except Exception as e:
    print ("I am in main exception handling")
    myLogger.log_exception(e, traceback)
    rxThreadObj.stop_thread = True


# wait for rx thread to join
rxThreadObj.stop_thread = True
dematicMsgHandlerObj.cancelTimer()
rxThreadObj.join(2.0)   # join timeout

myServer.close()
myLogger.log("Exiting Server.py")
myLogger.closeLogger()



