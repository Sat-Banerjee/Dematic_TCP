import util
import time
from queue import Queue
import traceback
from threading import Lock, Timer

class DematicMsgHandler():
    def __init__(self, qName, sockObj, logger, keepAliveTime, userOptsEnum, threadName=""):
        self.qId = qName
        self.sockObj = sockObj
        self.logger = logger
        self.tId = threadName
        self.keepAliveTime = keepAliveTime
        self.fSendKeepAlive = True
        self.keepAlivelock = Lock()
        self.sequenceCtr = 0
        self.sequenceLock = Lock()
        self.myTimer = None
        self.userOptsEnum = userOptsEnum

        self.bSTX = b'\x02'
        self.bCR = b'\x0D'
        self.bLF = b'\x0A'

        self.processing_fn_dict = dict()

        # callbacks to handle different types of messages
        self.processing_fn_dict["DATA"] = self.process_DATA_message
        self.processing_fn_dict["ACKN"] = self.process_ACKN_message
        self.processing_fn_dict["LIFE"] = self.process_LIFE_message
        self.processing_fn_dict["STAT"] = self.process_STAT_message

    def cancelTimer(self):
        try:
            if self.myTimer is not None:
                self.myTimer.cancel()
        except Exception as e:
            pass

    def startTimer(self):
        try:
            if self.myTimer is None:
                self.myTimer = Timer(self.keepAliveTime, self.send_KeepAliveMessage)
                self.myTimer.start()
        except Exception as e:
            self.logger.log_exception(e, traceback)


    def processUserInp(self, userInp):
        # do not process by val as this will be called by both server and client
        # the same val will mean differntly in both, hence work on the strings

        for opt in self.userOptsEnum:
            if (opt.value == userInp):
                self.processInp(opt.name)
                break

    def processInp(self, sInp):
        self.logger.log("{}: Processing input: {}".format(str(self.tId), sInp))

        if sInp == "UnArmed":
            self.send_Data_Message(strData="Unarm:001")
        
        elif sInp == "Request_to_move_Ranger":
            self.send_Data_Message(strData="mover:001")
        
        elif sInp == "Stop_Moving_Ranger":
            self.send_Data_Message(strData="mover:000")

        elif sInp == "Request_PLC_Status":
            self.send_Data_Message(strData="reqstat")

        elif sInp == "System_Armed":
            self.send_Data_Message(strData="armed:001")

        elif sInp == "System_UnArmed":
            self.send_Data_Message(strData="armed:000")

        elif sInp == "PLC_Status":
            self.send_Stat_Message(strData="statu:000")
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
        self.logger.log("{}: Processing message: {}".format(str(self.tId), str(message)))
        try:
            if self.validateMsg(sMessage=message):
                for mType, fnPtr in self.processing_fn_dict.items():
                    if mType in message:
                        fnPtr(message)
                        break
            else:
                self.logger.log("{}: Invalid message received, ignoring".format(str(self.tId)))
        except Exception as e:
            self.logger.log(e, traceback)

    def process_DATA_message(self, message):
        self.logger.log("{}: Processing a DATA message".format(str(self.tId)))
        # if ACKN needs to be sent
        strSequence = message[9:17] # 9-16 is the sequence number, py string truncate excludes upper bound
        intSequence = int(strSequence)
        if (intSequence != 0):
            self.send_ACKN_message(strSequence)

        #strMsgLen = len(message)
        strData = message[17:-1]
        self.processData(strData)


    def processData(self, strData):
        self.logger.log("{}: Processing data: {}".format(str(self.tId), strData))


    def process_ACKN_message(self, message):
        self.logger.log("{}: Processing an ACKN message".format(str(self.tId)))
    

    def process_LIFE_message(self, message):
        self.logger.log("{}: Processing a LIFE message".format(str(self.tId)))
    
    def process_STAT_message(self, message):
        self.logger.log("{}: Processing a STAT message".format(str(self.tId)))
    


    def sendMessage(self, message):
        self.sockObj.send_data(message)

        # set the send keepalive flag to false
        self.keepAlivelock.acquire()
        self.fSendKeepAlive = False
        self.keepAlivelock.release()

    # only if no messages has been sent in last 6 secs
    def send_KeepAliveMessage(self):
        if (self.fSendKeepAlive):
            # its similar to ACKN message, just the sequence no. is 0
            self.send_ACKN_message(strSequence="00000000", mType="LIFE")

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
        strMsg = strLen + str(mType) + self.__get_sequence_number() + strData

        bMsg = bytearray(strMsg)
        bMsg = self.bSTX + bMsg + self.bCR + self.bLF 
        strMsg = str(bMsg)
        
        return strMsg

    def send_Data_Message(self, strData):
        strMsg = self.prepareDematicStructuredData(mType="DATA", strData=strData)
        self.logger.log("{}: Sending Data message: {}".format(str(self.tId), strMsg))
        self.sendMessage(message=strMsg)

    def send_Stat_Message(self, strData):
        strMsg = self.prepareDematicStructuredData(mType="STAT", strData=strData)
        self.logger.log("{}: Sending Data message: {}".format(str(self.tId), strMsg))
        self.sendMessage(message=strMsg)


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


