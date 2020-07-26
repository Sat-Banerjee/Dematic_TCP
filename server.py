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
import os.path

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
# -------------------------------
# New CLI --
# -------------------------------
client_cli_parser = argparse.ArgumentParser(description="A simple TCP/IP Server. Currently implemented as a Dummy PLC which connects to a TCP/IP Client",
                                            epilog="for any issues, please contact Satyajeet Banerjee : satyajeet.b@greyorange.com\n")
client_cli_parser.version = "1.0"

# Positional Args
client_cli_parser.add_argument("ip", type=str, help="IP of the TCP/IP client you want to connect")
client_cli_parser.add_argument("port", type=int, help="Port of the TCP/IP client to which you want to connect")

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
# client_cli_parser.add_argument("-d51", "--disable_msg051_logs", action="store_false", help="Disable MSG051 logs. This logs the [outgoing] MSG052, MSG053 \
#                                                                                                 and [incoming] MSG051. Enabled by default")
# client_cli_parser.add_argument("-d54", "--disable_msg054_logs", action="store_false", help="Disable MSG054 logs. This logs the [incoming] MSG054. Enabled by default")
# client_cli_parser.add_argument("-d56", "--disable_msg056_logs", action="store_false", help="Disable MSG051 logs. This logs the [incoming] MSG056. Enabled by default")
client_cli_parser.add_argument("-k", "--keep_alive_time", action="store", type=float, default=6.0, help="Specify the LIFE message time interval. Defaults to 6.0 secs")
client_cli_parser.add_argument("-lf", "--logs_folder", action="store", type=str, default="./", help="Specify a folder for the logs to be saved. \
                                                                                                        Folder will be created if not found. \
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
if (not os.path.isdir(log_folder)):
    print ("\t ** The specified log folder: {} does not exist. Creating the folder.".format(log_folder))
    os.mkdir(log_folder)
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
enable_ack_logs = client_args.disable_ack_logs
print ("**** [Rx] ACK Logs: {}".format(str(enable_ack_logs)))
# --
enable_life_logs = client_args.disable_life_logs
print ("**** [Rx] LIFE Logs: {}".format(str(enable_life_logs)))
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
    myLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName= log_folder + "server_log" + file_timestamp + ".txt")

    if (enable_life_logs):
        myTimeLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName= log_folder + "server_life_rx_log" + file_timestamp + ".txt")
    else:
        myTimeLogger = None

    if (enable_ack_logs):
        myAckLogger = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName= log_folder + "server_ack_rx_log" + file_timestamp + ".csv")
    else:
        myAckLogger = None

    if (loop_time is not None):
        print ("Dummy Dematic PLC (Automated for Sending)")
        myLogger.log("\n{} ----------------- NEW SESSION Automated for Sending -----------------".format(str(util.getTimeStamp())))
    else:
        print ("Dummy Dematic PLC with user Options")
        myLogger.log("\n{} ----------------- NEW SESSION -----------------".format(str(util.getTimeStamp())))

except Exception as e:
    print (str(e))
    print (traceback.format_exc())
    sys.exit(-1)

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
    threadQ = Queue.Queue(maxsize=0)      # infinite size

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
                                    exp_data_size=500,
                                    threadName="RxThread")

    # create the Dematic processing thread 
    dematicThreadObj = Thread(target=dematicMsgHandlerObj.getAndProcessMessageFromQ)
    
    # start the dematic processing thread
    dematicThreadObj.start()

    # start the server, for incoming connections
    myServer.start_server()

    # start the rx thread 
    rxThreadObj.start()

    # timer
    dematicMsgHandlerObj.startTimer()

    while(not rxThreadObj.stop_thread):
        try:
            if loop_time is not None:
                dematicMsgHandlerObj.processUserInp(1)
                time.sleep (loop_time)
                dematicMsgHandlerObj.processUserInp(2)
                time.sleep (loop_time)
                dematicMsgHandlerObj.processUserInp(3)
                time.sleep (loop_time)
                dematicMsgHandlerObj.processUserInp(4)
                time.sleep (loop_time)
                dematicMsgHandlerObj.processUserInp(5)
                time.sleep (loop_time)
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
    dematicMsgHandlerObj.stopThread = True


# wait for rx thread to join
rxThreadObj.stop_thread = True
dematicMsgHandlerObj.stopThread = True
dematicMsgHandlerObj.cancelTimer()
rxThreadObj.join(2.0)   # join timeout
dematicThreadObj.join(2.0)

myServer.close()
myLogger.log("Exiting Server.py")
myLogger.closeLogger()



