import util
import time
import traceback
from threading import Thread
import RxThread
import DematicMsgHandler
#from multiprocessing import Queue
import Queue
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
    except KeyboardInterrupt as e:
        user_inp = 20
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
        threadQ.put((dematicHandler.processUserInp, user_inp))
        # dematicHandler.processUserInp(user_inp)    

    return retval

# ------------------------------------------------------------

# command line args
if (len(sys.argv) < 3):
    print ("Invalid no. of command line args. Usage python {} <ip> <port> <o: loop-time> <o: retry>".format(sys.argv[0]))
    exit(-1)

ip = str(sys.argv[1])
port = int(sys.argv[2])
connectionRetry = False
loopTime = None

keep_alive_time = 6  # secs
file_timestamp = util.getFormattedTimeStamp()
myLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./client_log_" + file_timestamp + ".txt")
myTimeLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./client_life_rx_log_" + file_timestamp + ".txt")
myAckLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./client_ack_rx_log_" + file_timestamp + ".csv")
msg_51_52_53_Logger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./client_msg_51_52_53_log_" + file_timestamp + ".txt")
msg_56_Logger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./client_msg_56_log_" + file_timestamp + ".txt")
msg_54_Logger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName="./client_msg_54_log_" + file_timestamp + ".txt")
myAckLogger.log("Timestamp, Sequence No., Data Direction, Data")

print ("------------------------------------------------------")
if (len(sys.argv) >= 4):
    loopTime = float(sys.argv[3])
    print ("Dummy GOR SERVER (Automated for Sending)")
    myLogger.log("\n{} ----------------- NEW SESSION Automated for Sending -----------------".format(str(util.getTimeStamp())))
else:
    print ("Dummy GOR SERVER with user Options")
    myLogger.log("\n{} ----------------- NEW SESSION -----------------".format(str(util.getTimeStamp())))
print ("------------------------------------------------------")

try:
    connectionRetry = bool (sys.argv[4])
except Exception as e:
    pass

myLogger.log ("Connection Retry: {}".format(str(connectionRetry)))

myClient = util.SockUtil(util.CONFIG.CLIENT, logger=myLogger, retry=connectionRetry)

myClient.create_socket()
myClient.connect_to_server(ip, port)

data = None
dataLen = 0

ctr = 1

try:
    # user opts
    opts = ClientUserOpts

    # create the Q for threads to communicate
    threadQ = Queue.Queue(maxsize=0)      # infinite size

    # Dematic Message Handler Obj
    dematicMsgHandlerObj = DematicMsgHandler.DematicMsgHandler(qName=threadQ,
                                                                userOptsEnum=opts,
                                                                sockObj=myClient,
                                                                logger=myLogger,
                                                                keepAliveTime=keep_alive_time,
                                                                threadName="DematicMsgHandler",
                                                                timeLogger=myTimeLogger,
                                                                ackLogger=myAckLogger,
                                                                msg_51_52_53_Logger=msg_51_52_53_Logger,
                                                                msg_56_Logger=msg_56_Logger,
                                                                msg_54_Logger=msg_54_Logger,
                                                                validateMessage=True,
                                                                iAmClient=True)

    # create the Rx thread obj
    rxThreadObj = RxThread.RxThread(qName=threadQ, 
                                    sockObj=myClient, 
                                    logger=myLogger,
                                    decodeFn=dematicMsgHandlerObj.process_Rx_Message,
                                    exp_data_size=500,
                                    #decodeFn=None,
                                    threadName="RxThread")

    # create the Dematic processing thread 
    dematicThreadObj = Thread(target=dematicMsgHandlerObj.getAndProcessMessageFromQ)
    
    # start the dematic processing thread
    dematicThreadObj.start()

    # start the rx thread 
    rxThreadObj.start()

    # start the timer
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
            else:
                user_inp = print_and_get_user_inp(opts)
                if (handle_user_inp(opts, user_inp, dematicHandler=dematicMsgHandlerObj) == -1):
                    break
        except KeyboardInterrupt as e:
            break
        except Exception as e:
            break

except Exception as e:
    myLogger.log_exception(e, traceback)
    rxThreadObj.stop_thread = True
    dematicMsgHandlerObj.stopThread = True

# wait for rx thread to join
rxThreadObj.stop_thread = True
dematicMsgHandlerObj.stopThread = True
dematicMsgHandlerObj.cancelTimer()
rxThreadObj.join(2.0)   # join timeout
dematicThreadObj.join(2.0)


myClient.close()
myLogger.log("Exiting Client.py")
myLogger.closeLogger()



