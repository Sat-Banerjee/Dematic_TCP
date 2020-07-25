import util
import time
import traceback
from threading import Thread
import RxThread
import DematicMsgHandler
import Queue
import sys
import enum
import argparse

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

# # command line args
# if (len(sys.argv) < 3):
#     print ("Invalid no. of command line args. Usage python {} <ip> <port> <o: loop-time> <o: retry>".format(sys.argv[0]))
#     exit(-1)

# ip = str(sys.argv[1])
# port = int(sys.argv[2])
# connectionRetry = False
# loopTime = None

# -------------------------------
# New CLI --
# -------------------------------
client_cli_parser = argparse.ArgumentParser(description="A simple TCP/IP Client. Currently implemented as a Dummy GOR Server which connects to a PLC/TCP Server",
                                            epilog="for any issues, please contact Satyajeet Banerjee : satyajeet.b@greyorange.com\n")
client_cli_parser.version = "1.0"

# Positional Args
client_cli_parser.add_argument("ip", type=str, help="IP of the TCP/IP server you want to connect")
client_cli_parser.add_argument("port", type=int, help="Port of the TCP/IP server to which you want to connect")

# Optional Args
client_cli_parser.add_argument("-cr", "--con_retry", action="store_true", help="Enable Connection Retry. Disabled by default")
client_cli_parser.add_argument("-lt", "--loop_time", action="store", type=float, help="Provide a time period for automated data packets transmission. If not, the user options are shown which \
                                                                                        allows for manual sending of data packets.\
                                                                                        Conflicts with logging to stdout [-ls]",
                                                                                        default=None)
client_cli_parser.add_argument("-dal", "--disable_ack_logs", action="store_false", help="Disable separate logging of the ACK messages received. \
                                                                                            Enabled by default")
client_cli_parser.add_argument("-dll", "--disable_life_logs", action="store_false", help="Disable separate logging of the LIFE messages received \
                                                                                            Enabled by default")                                                                        
client_cli_parser.add_argument("-d51", "--disable_msg051_logs", action="store_false", help="Disable MSG051 logs. This logs the [outgoing] MSG052, MSG053 \
                                                                                                and [incoming] MSG051. Enabled by default")
client_cli_parser.add_argument("-d54", "--disable_msg054_logs", action="store_false", help="Disable MSG054 logs. This logs the [incoming] MSG054. Enabled by default")
client_cli_parser.add_argument("-d56", "--disable_msg056_logs", action="store_false", help="Disable MSG051 logs. This logs the [incoming] MSG056. Enabled by default")
client_cli_parser.add_argument("-k", "--keep_alive_time", action="store", type=float, default=6.0, help="Specify the LIFE message time interval. Defaults to 6.0 secs")
client_cli_parser.add_argument("-lf", "--logs_folder", action="store", type=str, default="./", help="Specify a folder for the logs to be saved. \
                                                                                                        Defaults to the current dir")
client_cli_parser.add_argument("-dv", "--disable_validation", action="store_false", help="Disable incoming messages validation. \
                                                                                            Enabled by default.")
client_cli_parser.add_argument("-dct", "--disable_creation_timestamp", action="store_false", help="Don't add creation timestamp to log file name. \
                                                                                                Enabled by default.")
client_cli_parser.add_argument("-ls", "--log_to_stdout", action="store_true", help="Print all logs generated on STDOUT instead of log files.\
                                                                                        Disabled by default.")
# Parse the passed args
client_args = client_cli_parser.parse_args()

# ---------------------------------
print ("Using the following params for this session:")
print ("------------------------------------------")
# --
ip = client_args.ip
print ("**** IP: {}".format(ip))

port = client_args.port
print ("**** PORT: {}".format(str(port)))
# --
keep_alive_time = client_args.keep_alive_time  # secs
print ("**** Keep Alive Time: {} secs".format(str(keep_alive_time)))
# --
log_folder = client_args.logs_folder
print ("**** Logs Folder: {}".format(str(log_folder)))
# --
connectionRetry = client_args.con_retry
print ("**** Connection Retry: {}".format(str(connectionRetry)))
# --
loop_time = client_args.loop_time
if loop_time is not None:
    print ("**** Loop Time: {} secs".format(str(loop_time)))
else:
    print ("**** Loop disabled")
# --
message_validation = client_args.disable_validation
print ("**** Incoming Message Validation: {}".format(str(message_validation)))
# --
enable_creation_timestamp = client_args.disable_creation_timestamp
print ("**** enable_creation_timestamp: {}".format(str(enable_creation_timestamp)))
#--
log_to_stdout = client_args.log_to_stdout
print ("**** log to stdout: {}".format(str(log_to_stdout)))
# --
disable_ack_logs = client_args.disable_ack_logs
print ("**** [Rx] ACK Logs: {}".format(str(disable_ack_logs)))
# --
disable_life_logs = client_args.disable_life_logs
print ("**** [Rx] LIFE Logs: {}".format(str(disable_life_logs)))
# --
enable_51_logging = client_args.disable_msg051_logs
print ("**** MSG051 Logs: {}".format(str(enable_51_logging)))
enable_54_logging = client_args.disable_msg054_logs
print ("**** [Rx] MSG054 Logs: {}".format(str(enable_54_logging)))
enable_56_logging = client_args.disable_msg056_logs
print ("**** [Rx] MSG056 Logs: {}".format(str(enable_56_logging)))
# --
print ("------------------------------------------------------\n")

# Check for interconnected errors due to various CLI options 
if (log_to_stdout and (loop_time is None)):
    print ("* Cannot proceed because: Cannot show user options as logging to STDOUT is enabled.")
    sys.exit(-1)

# CLI parsing ends
# ---------------------------------# ---------------------------------

if enable_creation_timestamp:
    file_timestamp = "_" + util.getFormattedTimeStamp()
else:
    file_timestamp=""

if log_to_stdout:
    log_dest = util.LOG_DEST.STDOUT
    print ("--** WARNING **-- This will generate huge output on STDOUT.\n")
else:
    log_dest = util.LOG_DEST.FILE

if (log_folder[-1] != "/"):
    log_folder += "/"
try:
    myLogger = util.CustomLogger(log_dest=log_dest, fileName= log_folder + "client_log" + file_timestamp + ".txt")
    
    if (not disable_life_logs):
        myTimeLogger = util.CustomLogger(log_dest=log_dest, fileName= log_folder + "client_life_rx_log" + file_timestamp + ".txt")
    else:
        myTimeLogger = None

    if (not disable_ack_logs):
        myAckLogger = util.CustomLogger(log_dest=log_dest, fileName= log_folder + "client_ack_rx_log" + file_timestamp + ".csv")
        myAckLogger.log("Timestamp, Sequence No., Data Direction, Data")
    else:
        myAckLogger = None

    if (enable_51_logging):
        msg_51_52_53_Logger = util.CustomLogger(log_dest=log_dest, fileName= log_folder + "client_msg_51_52_53_log" + file_timestamp + ".txt")
    else:
        msg_51_52_53_Logger = None

    if (enable_56_logging):
        msg_56_Logger = util.CustomLogger(log_dest=log_dest, fileName= log_folder + "client_msg_56_log" + file_timestamp + ".txt")
    else:
        enable_56_logging = None

    if (enable_54_logging):
        msg_54_Logger = util.CustomLogger(log_dest=log_dest, fileName= log_folder + "client_msg_54_log" + file_timestamp + ".txt")
    else:
        msg_54_Logger = None

    if (loop_time is not None):
        print ("Dummy GOR SERVER (Automated for Sending)")
        myLogger.log("\n{} ----------------- NEW SESSION Automated for Sending -----------------".format(str(util.getTimeStamp())))
    else:
        print ("Dummy GOR SERVER with user Options")
        myLogger.log("\n{} ----------------- NEW SESSION -----------------".format(str(util.getTimeStamp())))

    myLogger.log ("Connection Retry: {}".format(str(connectionRetry)))
    myClient = util.SockUtil(util.CONFIG.CLIENT, logger=myLogger, retry=connectionRetry)
    myClient.create_socket()
    myClient.connect_to_server(ip, port)
except Exception as e:
    print (str(e))
    print (traceback.format_exc())
    sys.exit(-1)

print ("At 1")
data = None
dataLen = 0

ctr = 1
print ("At 2")
try:
    # user opts
    opts = ClientUserOpts

    # create the Q for threads to communicate
    threadQ = Queue.Queue(maxsize=0)      # infinite size
    print ("At 3")
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
                                                                validateMessage=message_validation,
                                                                iAmClient=True)
    print ("At 4")
    # create the Rx thread obj
    rxThreadObj = RxThread.RxThread(qName=threadQ, 
                                    sockObj=myClient, 
                                    logger=myLogger,
                                    decodeFn=dematicMsgHandlerObj.process_Rx_Message,
                                    exp_data_size=500,
                                    #decodeFn=None,
                                    threadName="RxThread")
    print ("At 5")
    # create the Dematic processing thread 
    dematicThreadObj = Thread(target=dematicMsgHandlerObj.getAndProcessMessageFromQ)
    print ("At 6")
    # start the dematic processing thread
    dematicThreadObj.start()
    print ("At 7")
    # start the rx thread 
    rxThreadObj.start()
    print ("At 8")
    # start the timer
    dematicMsgHandlerObj.startTimer()
    print ("At 9")
    while(not rxThreadObj.stop_thread):
        try:
            print ("At 10")
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
    print ("At 11. Ex")
    myLogger.log_exception(e, traceback)
    rxThreadObj.stop_thread = True
    dematicMsgHandlerObj.stopThread = True

print ("At 12")
# wait for rx thread to join
rxThreadObj.stop_thread = True
dematicMsgHandlerObj.stopThread = True
dematicMsgHandlerObj.cancelTimer()
rxThreadObj.join(2.0)   # join timeout
dematicThreadObj.join(2.0)


myClient.close()
myLogger.log("Exiting Client.py")
myLogger.closeLogger()



