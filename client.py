import util
import time
import traceback
from threading import Thread
import RxThread
import DematicMsgHandler
from queue import Queue
import sys
import enum

class ClientUserOpts(enum.IntEnum):
    Request_to_UnArm = 1,
    Request_to_Arm = 2,     # Same as Request to move Ranger
    #Stop_Moving_Ranger = 3,
    Request_PLC_Status = 3,
    Exit_App = 20

# --------------------------------------------------------
def print_and_get_user_inp(opts):
    user_inp = -1

    for msg in sorted(opts):
        print ("\t {:2} : {}".format(str(msg.value), str(msg.name)))

    try:
        user_inp = input ("\t Enter your Choice: ")
    except Exception as e:
        pass

    return int(user_inp)

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
print ("Dummy GOR SERVER")
print ("------------------------------------------------------")


keep_alive_time = 5  # secs

myLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./client_log.txt")
myTimeLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./life_rx_log.txt")
myAckLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./ack_rx_log.csv")
myAckLogger.log("Timestamp, Ackn No., Data Direction, Data")
myLogger.log("\n----------------- NEW SESSION (without ValidateMessage, Enable it asap) -----------------")
myClient = util.SockUtil(util.CONFIG.CLIENT, logger=myLogger)

myClient.create_socket()
myClient.connect_to_server(ip, port)

data = None
dataLen = 0

ctr = 1

try:
    # user opts
    opts = ClientUserOpts

    # create the Q for threads to communicate
    threadQ = Queue(maxsize=0)      # infinite size

    # Dematic Message Handler Obj
    dematicMsgHandlerObj = DematicMsgHandler.DematicMsgHandler(qName=threadQ,
                                                                userOptsEnum=opts,
                                                                sockObj=myClient,
                                                                logger=myLogger,
                                                                keepAliveTime=keep_alive_time,
                                                                threadName="DematicMsgHandler",
                                                                timeLogger=myTimeLogger,
                                                                ackLogger=myAckLogger,
                                                                validateMessage=True)

    # create the Rx thread obj
    rxThreadObj = RxThread.RxThread(qName=threadQ, 
                                    sockObj=myClient, 
                                    logger=myLogger,
                                    decodeFn=dematicMsgHandlerObj.process_Rx_Message, 
                                    threadName="RxThread")

    # start the rx thread 
    rxThreadObj.start()

    # start the timer
    dematicMsgHandlerObj.startTimer()

    while(not rxThreadObj.stop_thread):
        user_inp = print_and_get_user_inp(opts)
        if (handle_user_inp(opts, user_inp, dematicHandler=dematicMsgHandlerObj) == -1):
            break

except Exception as e:
    myLogger.log_exception(e, traceback)
    rxThreadObj.stop_thread = True


# wait for rx thread to join
rxThreadObj.stop_thread = True
dematicMsgHandlerObj.cancelTimer()
rxThreadObj.join(2.0)   # join timeout

myClient.close()
myLogger.log("Exiting Client.py")
myLogger.closeLogger()



