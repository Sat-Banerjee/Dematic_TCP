import util
import time
import datetime
from multiprocessing import Queue
import traceback
from threading import Lock, Timer

class DematicMsgHandler():
    def __init__(self, qName, sockObj, logger, 
                    keepAliveTime, userOptsEnum, threadName="", 
                    **kwargs):            
                    # timeLogger=None, validateMessage=True):
        
        self.qId = qName
        self.sockObj = sockObj
        self.logger = logger
        self.tId = threadName
        self.keepAliveTime = keepAliveTime
        self.fSendKeepAlive = True
        self.keepAlivelock = Lock()
        self.sequenceCtr = int (kwargs.get("seq_start_from", 0))
        self.sequenceLock = Lock()
        self.myTimer = None
        self.userOptsEnum = userOptsEnum
        self.validateMessage = kwargs.get("validateMessage", True)
        self.timeLogger = kwargs.get("timeLogger", None)
        self.ackLogger = kwargs.get("ackLogger", None)
        #self.seq_start_from = int (kwargs.get("seq_start_from", 0))
        self.lastLifeAt = util.getTimeStamp()
        self.ackList = list()
        self.myLifeCtr = 0

        # ----- counters for life timing -- 
        self.totalLifeMsg = 0
        self.life6AndBelow = 0      # correct messages which came under 6 secs
        self.lifeBelow6_1 = 0       # messages which came under 6.1 secs
        self.lifeBelow6_2 = 0       # messages which came under 6.2 secs
        self.lifeBelow6_5 = 0       # messages which came under 6.5 secs
        self.lifeAbove6_5 = 0       # messages which came after 6.5 secs
        # ---------------------------------

        self.bSTX = b'\x02'
        self.bCR = b'\x0D'
        self.bLF = b'\x0A'

        self.processing_fn_dict = dict()

        # callbacks to handle different types of messages
        self.processing_fn_dict["DATA"] = self.process_DATA_message
        self.processing_fn_dict["ACKN"] = self.process_ACKN_message
        self.processing_fn_dict["LIFE"] = self.process_LIFE_message
        self.processing_fn_dict["STAT"] = self.process_STAT_message

        self.logger.log("{}: Incoming Message Validation set to: {}".format(str(self.tId), str(self.validateMessage)))            

    def cancelTimer(self):
        try:
            if self.myTimer is not None:
                self.myTimer.cancel()
        except Exception as e:
            pass

    def startTimer(self):
        try:
            #if self.myTimer is None:
            self.myTimer = Timer(self.keepAliveTime, self.send_KeepAliveMessage)
            self.myTimer.start()
            # else:
            #     self.logger.log("{}: myTimer is not None on expiry".format(str(self.tId)))
        except Exception as e:
            self.logger.log_exception(e, traceback)


    def processUserInp(self, userInp):
        # do not process by val as this will be called by both server and client
        # the same val will mean differntly in both, hence work on the strings

        for opt in self.userOptsEnum:
            if (opt.value == userInp):
                self.processInp(opt.name)
                break

    def getStationId(self):
        return "0151"

    def processInp(self, sInp):
        self.logger.log("{}: Handling User input: {}".format(str(self.tId), sInp))

        if sInp == "Request_to_UnArm":
            strData = str(self.getStationId()) + "MSG052peripheral_groupid01peripheral_type001timestamp" + util.getFormattedTimeStamp() 
            self.send_Data_Message(strData=strData)
        
        elif sInp == "Request_to_Arm":  # Same as Request to move Ranger
            strData = str(self.getStationId()) + "MSG053peripheral_groupid01peripheral_type001timestamp" + util.getFormattedTimeStamp() 
            self.send_Data_Message(strData=strData)
        
        elif sInp == "Peripheral_Emergency_Active":
            strData = str(self.getStationId()) + "MSG054peripheral_groupid01peripheral_type001emergency001timestamp" + util.getFormattedTimeStamp() 
            self.send_Data_Message(strData=strData)

        elif sInp == "Peripheral_Emergency_Resolved":
            strData = str(self.getStationId()) + "MSG054peripheral_groupid01peripheral_type001emergency000timestamp" + util.getFormattedTimeStamp() 
            self.send_Data_Message(strData=strData)

        # elif sInp == "Stop_Moving_Ranger":
        #     self.send_Data_Message(strData="mover:000")

        elif sInp == "Request_PLC_Status":
            strData = str(self.getStationId()) + "MSG055peripheral_groupid01peripheral_type001timestamp" + util.getFormattedTimeStamp() 
            self.send_Data_Message(strData=strData)

        elif sInp == "System_Armed":
            strData = str(self.getStationId()) + "MSG051peripheral_groupid01peripheral_type001armed001timestamp" + util.getFormattedTimeStamp() 
            self.send_Data_Message(strData=strData)

        elif sInp == "System_UnArmed":
            strData = str(self.getStationId()) + "MSG051peripheral_groupid01peripheral_type001armed000timestamp" + util.getFormattedTimeStamp() 
            self.send_Data_Message(strData=strData)

        elif sInp == "PLC_Status_Response":
            strData = str(self.getStationId()) + "MSG056peripheral_groupid01peripheral_type001armed000emergency001status001timestamp" + util.getFormattedTimeStamp() 
            self.send_Data_Message(strData=strData)

        else:
            self.logger.log("{}: Wrong User Input: {}".format(str(self.tId), sInp))


    # sequence no.'s are 8 bytes long
    def __get_sequence_number(self):
        strSequence = ""

        self.keepAlivelock.acquire()
        self.sequenceCtr += 1
        self.keepAlivelock.release()

        strSequence = str(self.sequenceCtr)
        strSequence = self.__packData(strSequence, 8)
        return strSequence

    def __packData(self, strData, expSize):
        initLen = len(strData)

        while (initLen < expSize):
            strData = "0" + strData
            initLen += 1

        return strData
        
    def process_Rx_Message(self, message):
        self.logger.log("{} {}: Processing message: {}".format(str(util.getTimeStamp()), str(self.tId), str(message)))
        try:
            if ((not self.validateMessage) or (self.validateMsg(sMessage=message))):
                for mType, fnPtr in self.processing_fn_dict.items():
                    if mType in message:
                        fnPtr(message)
                        break
            elif (not self.validateMsg(sMessage=message)):
                # check if multiple messages are received ?
                count = message.count(str(self.bSTX))
                if count > 1 : 
                    # we have received multiple messages
                    self.logger.log("{}: Multiple ({}) Messages Received".format(str(self.tId), str(count)))
                    searchMsg = message
                    while (searchMsg.find(str(self.bSTX)) != -1):
                        # starts with STX
                        partSize = int(searchMsg[1:5])
                        partMessage = searchMsg[:partSize]
                        self.process_Rx_Message(message=partMessage)
                        searchMsg = searchMsg[partSize:]
            else:
                self.logger.log("{}: Invalid message received, ignoring".format(str(self.tId)))
        except Exception as e:
            self.logger.log_exception(e, traceback)

    def process_DATA_message(self, message):
        self.logger.log("{}: Processing a DATA message".format(str(self.tId)))
        # if ACKN needs to be sent
        strSequence = message[9:17] # 9-16 is the sequence number, py string truncate excludes upper bound
        intSequence = int(strSequence)
        if (intSequence != 0):
            self.logger.log("{}: Need to send ACKN for sequence: {}".format(str(self.tId), strSequence))
            self.send_ACKN_message(strSequence)

        #strMsgLen = len(message)
        strData = message[17:-1]
        self.processData(strData)


    def processData(self, strData):
        self.logger.log("{}: Processing data: {}".format(str(self.tId), strData))


    def process_ACKN_message(self, message):
        self.logger.log("{}: Processing an ACKN message".format(str(self.tId)))
        ackNo = message[9:]
        ackNo = ackNo[:-2]
        if self.ackLogger is not None:
            self.ackLogger.log("{}, {}, Received ACKN, {}".format(str(util.getTimeStamp()), str(int(ackNo)), message))

        if ackNo in self.ackList:
            self.logger.log("{}: ACKN sequence ({}) matching".format(str(self.tId), str(ackNo)))
            self.ackList.remove(ackNo)
        else:
            self.logger.log("{}: ERROR -- ACKN sequence ({}) not matching".format(str(self.tId), str(ackNo)))


    def process_LIFE_message(self, message):
        self.totalLifeMsg += 1
        currTime = util.getTimeStamp()
        self.logger.log("{} {}: Processing a LIFE message".format(str(currTime), str(self.tId)))
        
        if self.timeLogger is not None:
            timeDiff = currTime - self.lastLifeAt
            self.timeLogger.log("{}: Processing a LIFE message. Diff: {}".format(str(currTime), str(timeDiff)))
        
            if (timeDiff > 6):
                self.timeLogger.log("**ERROR** Last Life at: {}, Curr Life at: {}, Time Diff: {}".format(str(self.lastLifeAt),
                                                                                                        str(currTime),
                                                                                                        str(timeDiff)))
                if (timeDiff <= 6.1):
                    self.lifeBelow6_1 += 1
                elif (timeDiff <= 6.2):
                    self.lifeBelow6_2 += 1
                elif (timeDiff <= 6.5):
                    self.lifeBelow6_5 += 1
                else:
                    self.lifeAbove6_5 += 1
            
            else:
                # Correct Life
                self.life6AndBelow += 1

            self.timeLogger.log("Total Life: {}, Correct Life: {}, Below 6.1: {}, Below 6.2: {}, Below 6.5: {}, Above 6.5: {}".format(
                                    str(self.totalLifeMsg),
                                    str(self.life6AndBelow),
                                    str(self.lifeBelow6_1),
                                    str(self.lifeBelow6_2),
                                    str(self.lifeBelow6_5),
                                    str(self.lifeAbove6_5)
                                    ))

            self.lastLifeAt = currTime


    def process_STAT_message(self, message):
        self.logger.log("{}: Processing a STAT message".format(str(self.tId)))
        # if ACKN needs to be sent
        strSequence = message[9:17] # 9-16 is the sequence number, py string truncate excludes upper bound
        intSequence = int(strSequence)
        if (intSequence != 0):
            self.send_ACKN_message(strSequence)

        #strMsgLen = len(message)
        strData = message[17:-1]
        self.processData(strData)

    def sendMessage(self, message):
        self.sockObj.send_data(message)

        # set the send keepalive flag to false
        self.keepAlivelock.acquire()
        self.fSendKeepAlive = False
        self.keepAlivelock.release()


    def send_KeepAliveMessage(self):
        #if (self.fSendKeepAlive):
        self.myLifeCtr += 1
        # its similar to ACKN message, just the sequence no. is 0
        self.send_ACKN_message(strSequence="00000000", mType="LIFE")
        self.logger.log("{}: My Life Ctr: {}".format(str(self.tId), str(self.myLifeCtr)))
        self.keepAlivelock.acquire()
        self.fSendKeepAlive = True
        self.keepAlivelock.release()

        # start the timer, again
        self.startTimer()

    # as this fn is reused for life messages as well
    def send_ACKN_message(self, strSequence, mType="ACKN"):
        strAcknMsg = "0019" + str(mType) + str(strSequence)
        bAcknMsg = self.bSTX + bytearray(strAcknMsg) + self.bCR + self.bLF
        # convert back to str, to send
        strAcknMsg = str(bAcknMsg)
        self.sendMessage(strAcknMsg)

    def prepareDematicStructuredData(self, mType, strData):
        # total len = data len + 4 (for msg id "DATA") + 3 (STX, CR, Lf) + 4 (for SIZE) + 8 (for seq. no)
        total_len = len(strData) + 19
        strLen = str(total_len)
        strLen = self.__packData(strLen, 4)

        # without CR, LF, STX. That will be added later
        seqNo = self.__get_sequence_number()
        strMsg = strLen + str(mType) + seqNo + strData

        bMsg = bytearray(strMsg)
        bMsg = self.bSTX + bMsg + self.bCR + self.bLF 
        strMsg = str(bMsg)
        self.ackList.append(seqNo)
        return (strMsg, seqNo)

    def send_Data_Message(self, strData):
        strMsg, seqNo = self.prepareDematicStructuredData(mType="DATA", strData=strData)
        self.logger.log("{}: Sending Data message: {}".format(str(self.tId), strMsg))
        if self.ackLogger is not None:
            self.ackLogger.log("{}, {}, Sending Data, {}".format(str(util.getTimeStamp()), str(seqNo), strMsg))

        self.sendMessage(message=strMsg)

        self.logger.log("{}: Pending ack to match: {}".format(str(self.tId), str(len(self.ackList))))  
        # log the pending acks if any 
        if (len(self.ackList) > 0):
            self.logger.log("----------------------------------------")
            for ack in self.ackList:
                self.logger.log("{} , ".format(ack), newLine=False)

        self.logger.log("", newLine=True)
        self.logger.log("----------------------------------------")
        self.logger.log("", newLine=True)

    def send_Stat_Message(self, strData):
        strMsg, seqNo = self.prepareDematicStructuredData(mType="STAT", strData=strData)
        self.logger.log("{}: Sending Stat message: {}".format(str(self.tId), strMsg))
        self.sendMessage(message=strMsg)

        self.logger.log("{}: Pending ack to match: {}".format(str(self.tId), str(len(self.ackList))))  
        # log the pending acks if any 
        if (len(self.ackList) > 0):
            self.logger.log("----------------------------------------")
            for ack in self.ackList:
                self.logger.log("{}, ".format(ack), newLine=False)

        self.logger.log("", newLine=True)
        self.logger.log("----------------------------------------")
        self.logger.log("", newLine=True)


    def validateMsg(self, sMessage):
        # index 0 -> <STX> char \x02
        # end 2 chars -> <CR><LF> \x0D \x0A
        # check message len
        retval = True
        try:
            msgLeninData = int(sMessage[1:5])
            actualLen = len(sMessage)
            bMessage = bytearray(sMessage)

            if (msgLeninData != actualLen):
                self.logger.log("{}: Data length mismatch, {} & {}".format(str(self.tId), str(msgLeninData), str(actualLen)))
                retval = False
            elif (bMessage[0] != ord(self.bSTX)):
                self.logger.log("{}: STX byte missing".format(str(self.tId)))
                retval = False
            elif (bMessage[-1] != ord(self.bLF)):
                self.logger.log("{}: LF byte missing".format(str(self.tId)))
                retval = False
            elif (bMessage[-2] != ord(self.bCR)):
                self.logger.log("{}: CR byte missing".format(str(self.tId)))
                retval = False

        except Exception as e:
            self.logger.log_exception(e, traceback)
            retval = False

        return retval


