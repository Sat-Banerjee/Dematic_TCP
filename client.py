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
    UnArmed = 1,
    Request_to_move_Ranger = 2,
    Stop_Moving_Ranger = 3,
    Request_PLC_Status = 4,
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
print ("Dummy GO SERVER")
print ("------------------------------------------------------")


keep_alive_time = 15  # secs

myLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./client_log.txt")
myLogger.log("\n----------------- NEW SESSION -----------------")
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
                                                                threadName="DematicMsgHandler")

    # start the timer
    dematicMsgHandlerObj.startTimer()

    # create the Rx thread obj
    rxThreadObj = RxThread.RxThread(qName=threadQ, 
                                    sockObj=myClient, 
                                    logger=myLogger,
                                    decodeFn=dematicMsgHandlerObj.process_Rx_Message, 
                                    threadName="RxThread")

    # start the rx thread 
    rxThreadObj.start()

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



