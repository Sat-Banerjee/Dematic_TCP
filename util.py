import socket
import sys
import enum
import traceback
import fcntl, os
import errno

class LOG_DEST(enum.IntEnum):
    NO_LOG = 0
    FILE = 1
    STDOUT = 2

class CONFIG(enum.IntEnum):
    CLIENT = 1
    SERVER = 2

class CustomLogger():
    def __init__(self, log_dest, fileName=None):
        self.log_dest = log_dest
        self.fileName = fileName
        self.file_obj = None
        self.disable = False

        if (self.log_dest == LOG_DEST.FILE):
            self.file_obj = open(self.fileName, "a+")

    def logs(self, disable):
        self.disable = disable

    def closeLogger(self):
        if (self.log_dest == LOG_DEST.FILE) and (self.file_obj is not None):
            self.file_obj.close()
            self.file_obj = None    

    def log(self, message):
        if not self.disable:
            if (self.log_dest == LOG_DEST.NO_LOG):
                pass
            elif (self.log_dest == LOG_DEST.STDOUT):
                print (message)
            elif (self.log_dest == LOG_DEST.FILE):
                self.file_obj.write(str(message) + "\n")
                self.file_obj.flush()

    def log_exception(self, e, traceback):
        self.log(e.message)
        self.log(traceback.format_exc())

class SockUtil():
    def __init__(self, config, rx_fn=None, enable_logs=True, logger=None):
        self.sock = None
        self.sConnection = None
        self.sClientAddress = None
        self.rx_callback = rx_fn
        self.config = config
        self.outputFileName = None if logger is not None else str("./" + str(config.name) +"_util_logs.txt")
        self.logger = logger if logger is not None else CustomLogger(log_dest=LOG_DEST.FILE, fileName=self.outputFileName)
        self.logger.logs(disable= (not enable_logs))

    def create_socket(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # reuse the socket if available, helps if the previous conneciton was not terminated gracefully.
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.logger.log("Created a Socket")
        except Exception as e:
            self.logger.log_exception(e, traceback)

    def bind(self, ip, port):
        try:
            serverAddress = (str(ip), int (port))
            self.sock.bind(serverAddress)
            self.logger.log("Sucessfully binded with the ip: {}, port: {}".format(str(ip), str(port)))
        except Exception as e:
            self.logger.log_exception(e, traceback)

    def start_server(self):
        try:
            if (self.config == CONFIG.SERVER):
                # listen for incoming connections
                self.logger.log("Listening for incoming connections")
                self.sock.listen(1)

                # wait for a connection
                self.logger.log("Wating for a connection")
                self.sConnection, self.sClientAddress = self.sock.accept()
                self.logger.log("Connection from: {}".format(str(self.sClientAddress)))
                # non blocking socket
                fcntl.fcntl(self.sConnection, fcntl.F_SETFL, os.O_NONBLOCK)

            else:
                self.logger.log("I am configured as CLIENT, cannot call start_server()")
        except Exception as e:
            self.logger.log_exception(e, traceback)

    def __stop_server(self):
        try:
            if (self.config == CONFIG.SERVER):
                self.sConnection.close()            
            else:
                self.logger.log("I am configured as CLIENT, cannot call stop_server()")
        except Exception as e:
            self.logger.log_exception(e, traceback)

    def close(self):
        self.logger.log("Closing Connections")
        if self.config == CONFIG.SERVER:
            self.__stop_server()
        
        self.sock.close()
        self.logger.log("Connection Closed")

    # called by a client
    def connect_to_server(self, ip, port):
        try:
            if (self.config == CONFIG.CLIENT):
                serverAddress = (str(ip), port)
                self.logger.log("Connecting to: {} : {}".format(str(ip), port))
                self.sock.connect(serverAddress)
                # non blocking socket
                fcntl.fcntl(self.sock, fcntl.F_SETFL, os.O_NONBLOCK)

            else:
                self.logger.log("I am configured as SERVER, cannot call connect_to_server()")
        except Exception as e:
            self.logger.log("Error connecting to Server" + e.message)
            self.logger.log_exception(e, traceback)

    def send_data(self, message):
        try:
            if self.config == CONFIG.CLIENT:
                self.logger.log("(as client) Sending message: {}".format(message))
                self.sock.sendall(str(message))
            else:
                self.logger.log("(as server) Sending message: {}".format(message))
                self.sConnection.sendall(str(message))

        except Exception as e:
            err = e.args[0]

            if (err == errno.ECONNRESET) or \
                (err == errno.ECONNABORTED) or \
                (err == errno.EPIPE):
                raise e
            else:
                self.logger.log_exception(e, traceback)


    def receive_data(self, expected_data_len):
        data_received = 0
        data = None

        #self.logger.log("Received data: {} bytes".format(data_received))

        while (data_received < expected_data_len):
            try:
                if self.config == CONFIG.CLIENT:
                    data = self.sock.recv(expected_data_len)
                else:
                    # server
                    data = self.sConnection.recv(expected_data_len)

                if data:
                    data_received += len(data)
                    self.logger.log("Receiving data: {} bytes, data: {}".format(data_received, data))
                else:
                    #self.logger.log("No more data coming from {}".format(self.sClientAddress))
                    raise (Exception(errno.ECONNABORTED))

            except Exception as e:
                err = e.args[0]
                if (err == errno.EAGAIN) or (err == errno.EWOULDBLOCK):
                    #self.logger.log("No data available on port")
                    break

                elif (err == errno.ECONNRESET) or \
                (err == errno.ECONNABORTED) or \
                (err == errno.EPIPE):
                    raise e

            #break

        return (data, data_received)