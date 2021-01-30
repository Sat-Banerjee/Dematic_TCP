from threading import Thread
import util
#from multiprocessing import Queue
import Queue
import time
import traceback

class RxThread(Thread):
    def __init__(self, qName, sockObj, logger, decodeFn, exp_data_size=300, threadName="default"):
        Thread.__init__(self)
        self.qId = qName
        self.tId = threadName
        self.sockObj = sockObj
        self.logger = logger
        self.decodeFn = decodeFn
        self.exp_data_size = exp_data_size
        self.stop_thread = False

    def run(self):
        data = None
        dataLen = 0
        # See the socket for any rx data and add to the given queue
        while not self.stop_thread:
            try:
                data, dataLen = self.sockObj.receive_data(expected_data_len=self.exp_data_size)
    
                if data is not None:
                    self.logger.log("{} - {}: data received {} bytes: {}".format(str(util.getTimeStamp()), str(self.tId), str(dataLen), data))
                    self.qId.put((self.decodeFn, data))
                else:
                    time.sleep(0.300)   # 300 ms
            except Exception as e:
                self.logger.log_exception(e, traceback)
                # only errors which could not be handled internally are thrown, hence quit now
                self.stop_thread = True

        self.logger.log("{} : Exiting thread".format(str(self.tId)))