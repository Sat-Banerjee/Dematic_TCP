from __future__ import division
import sys
import glob
import util
import traceback
import json

def do_underline(file, line_to_underline):
    underL = ""
    for i in range(len(line_to_underline)):
        underL += "*"
    file.log(underL)


def handleFiles(log_dir, timestamp, report):
    ack_filename = None
    client_log_filename = None

    for fileName in glob.glob(log_dir + "/" + "client*_" + timestamp + "*"):
        # print ("Handling file: " + fileName)
        if ("51_52_53" in fileName):
            handle_Msg_51_log_file(fileName, report)
        elif ("life_rx_log" in fileName):
            handle_life_rx_log_file(fileName, report)
        elif ("client_log" in fileName):
            #handle_client_log_file(fileName, report)
            client_log_filename = fileName
        elif ("msg_54" in fileName):
            handle_Msg_54_log_file(fileName, report)
        elif ("msg_56" in fileName):
            handle_Msg_56_log_file(fileName, report)
        elif ("ack_rx" in fileName):
            # handle_ack_rx_log_file(fileName, report)
            ack_filename = fileName
        elif ("tcpdump" in fileName):
            pass
        else:
            print ("{} not recognized as a valid log file")

    # call the client log file handler along with the ack filename
    print (client_log_filename)
    print (ack_filename)
    handle_client_log_file(log_fileName=client_log_filename, ack_filename=ack_filename, report=report)


def handle_Msg_51_log_file(fileName, report):
    print ("Handling a MSG 51 52 53 log file: " + fileName)

    try:
        fd = open(fileName, "r")
        lines = fd.readlines()

        str_1_handled = False
        str_2_handled = False
        
        report.log("Report - MSG051 RX from PLC, MSG052 & MSG052 TX to PLC")
        do_underline(report, "Report - MSG051 RX from PLC, MSG052 & MSG052 TX to PLC")

        for line in reversed(lines):
            search_str1 = "Received"
            search_str2 = "Sending"
            if (search_str1 in line):
                ptr = line.find("Rx ctr: ")
                total_51_rx = int(line[ptr+len("Rx ctr: "):len(line)])
                # print ("Total MSG051 Rx from PLC: {}".format(str(total_51_rx)))
                report.log("Total MSG051 Rx from PLC: {}".format(str(total_51_rx)))
                str_1_handled = True
            
            elif (search_str2 in line):
                ptr = line.find("MSG052 Tx Count: ")
                ptrC = line.find(",")
                total_52_tx = int(line[ptr+len("MSG052 Tx Count: "):ptrC])

                ptr = line.find("MSG053 Tx Count: ") 
                total_53_tx = int(line[ptr+len("MSG053 Tx Count: "):len(line)])

                #print ("Total MSG054 Rx from PLC: {}".format(str(total_54_rx)))
                report.log("Total MSG052 Tx to PLC: {}".format(str(total_52_tx)))
                report.log("Total MSG053 Tx to PLC: {}".format(str(total_53_tx)))
                str_2_handled = True

            if (str_1_handled and str_2_handled):
                break

        total_tx_msgs = total_52_tx + total_53_tx
        extra_msgs = total_51_rx - total_tx_msgs
        report.log("Total (MSG052,53) Tx Msgs to PLC: {}".format(str(total_tx_msgs)))
        report.log("Extra Msgs ( Rx-Tx): {}".format(str(extra_msgs)))
        report.log("\n-----------------------------------------------------------------------")

        fd.close()
    except Exception as e:
        print (e.message)


def handle_life_rx_log_file(fileName, report):
    print ("Handling a PLC life rx log file: " + fileName)

    try:
        fd = open(fileName, "r")
        lines = fd.readlines()

        for line in reversed(lines):
            search_str = "Total Life:"
            if (search_str in line):
                ptr1 = line.find(",")
                total_life = int(line[len(search_str):ptr1])

                ptr2 = line.find("Above 6.5: ")
                life_above_6_5 = int(line[(ptr2 + len("Above 6.5: ")):len(line)])

                print ("Total life: {}, life_above_6.5: {}".format(str(total_life), str(life_above_6_5)))

                report.log("Report - LIFE RX from PLC")
                do_underline(report, "Report - LIFE RX from PLC")
                report.log("Total Life Rx: {}".format(str(total_life)))
                report.log("Life Msgs above 6.5 secs: {}".format(str(life_above_6_5)))
                p_error = round(((life_above_6_5/total_life) * 100), 2)
                report.log("%age error: {}%".format(str(p_error)))
                report.log("\n-----------------------------------------------------------------------")

                break

        fd.close()
    except Exception as e:
        print (e.message)


def parse_pending_ack_str(log_str):
    pendingAckList = []

    pendingAckStrList = log_str.split(",")

    for ack in pendingAckStrList:
        # print ack
        try:
            pendingAckList.append(int(ack.strip()))
        except Exception as e:
            pass

    # sort the list
    pendingAckList.sort()

    return pendingAckList

def handle_client_log_file(log_fileName, ack_filename, report):
    print ("Handling a client log file: " + log_fileName)

    total_data_msgs_to_plc = parse_ack_rx_log_file(fileName=ack_filename)

    pendingAckList = []
    parse_line = False
    read_count = False
    count_read = False
    counted_life = False
    can_we_break = False

    try:
        fd = open(log_fileName, "r")
        lines = fd.readlines()

        report.log("Report - Pending Ack's from PLC")
        do_underline(report, "Report - Pending Ack's from PLC")

        for line in reversed(lines):
            search_str = "--------------------------"
            if (search_str in line):
                if not parse_line:
                    parse_line = True
                else:
                    # parse line is true, hence we have already parsed the pending ack str's
                    parse_line = False
                    read_count = True
            
            elif parse_line:
                # this line contains the delimited string for all the pending acks 
                pendingAckList = parse_pending_ack_str(line)
            
            elif read_count:
                read_count = False
                ptr = line.find("to match: ")
                count = int(line[ptr+len("to match: "):len(line)])

                if (count == len(pendingAckList)):
                    # Parsing went OK
                    print ("Parsing OK")

                count_read = True
            
            elif ("My Life Ctr: " in line):
                ptrL = line.find("My Life Ctr: ")
                lifeCount = line[ptrL+len("My Life Ctr: "):len(line)]
                report.log("Total Life Msgs Sent to PLC: {}".format(lifeCount))
                counted_life = True

            if count_read and counted_life: 
                can_we_break = True

            if can_we_break:
                break            

        report.log("Total Data Msgs Tx to PLC: {}".format(str(total_data_msgs_to_plc)))
        report.log("Total Ack Missed: {}".format(str(len(pendingAckList))))
        p_miss = round(((len(pendingAckList)/total_data_msgs_to_plc) * 100), 2)
        report.log("%age Misses: {}%".format(str(p_miss)))

        arm000_error_count = 0
        arm001_error_count = 0

        arm000_request = 0
        arm000_response = 0
        arm001_request = 0
        arm001_response = 0

        error_classification_dict = dict()

        for line in lines:
            if "DematicMsgHandler: Handling User input: Request_to_UnArm" in line:
                arm000_error_count += 1
                arm000_request += 1
            elif "DematicMsgHandler: Handling User input: Request_to_Arm" in line:
                arm001_error_count += 1
                arm001_request += 1
            elif "DematicMsgHandler: Processing data" in line:
                if "MSG051" in line:
                    if "armed000" in line:
                        arm000_error_count -= 1
                        arm000_response += 1
                    elif "armed001" in line:
                        arm001_error_count -= 1
                        arm001_response += 1                        
            elif "DematicMsgHandler: Sending Data message:" in line:
                # this is a data msg sent from client -> PLC
                if (len(pendingAckList) > 0):
                    if str(pendingAckList[0]) in line:
                        # if this is the msg for which ACK was not received
                        ptr1 = line.find("peripheral")
                        msgFormat = "MSGxxx"
                        msgType = line[ptr1-len(msgFormat):ptr1]
                        #print ("{}: {}".format(str(pendingAckList[0]), msgType))
                        pendingAckList.pop(0)

                        if msgType in error_classification_dict.keys():
                            error_classification_dict[msgType] = error_classification_dict[msgType] + 1
                        else:
                            error_classification_dict[msgType] = 1

        report.log("\nThe below data indicates error counts for arm000 and arm001 tasks. +ve count means client sent more requests but received less MSG051, and vice versa.")
        report.log("armed000_error_count: {}, armed001_error_count: {}\n".format(str(arm000_error_count), str(arm001_error_count)))

        report.log("Below data clearly indicates how many arm/unarm requests were sent, and how many responses received")
        report.log("ARM  :-- request: {}, response: {}, difference: {}".format(str(arm000_request), str(arm000_response), str(arm000_request-arm000_response)))
        report.log("UNARM:-- request: {}, response: {}, difference: {}".format(str(arm001_request), str(arm001_response), str(arm001_request-arm001_response)))

        report.log("\nBelow is the classification of the pending acks-")
        error_classification_str = json.dumps(error_classification_dict)

        report.log(error_classification_str)

        report.log("\n-----------------------------------------------------------------------")

        fd.close()
    except Exception as e:
        print (e.message)
        print (traceback.format_exc())



def handle_Msg_54_log_file(fileName, report):
    print ("Handling a MSG 54 log file: " + fileName)

    try:
        fd = open(fileName, "r")
        lines = fd.readlines()

        for line in reversed(lines):
            search_str = "Rx ctr: "
            if (search_str in line):
                ptr = line.find(search_str)
                total_54_rx = int(line[ptr+len(search_str):len(line)])

                print ("Total MSG054 Rx from PLC: {}".format(str(total_54_rx)))

                report.log("Report - MSG054 RX from PLC")
                do_underline(report, "Report - MSG054 RX from PLC")
                report.log("Total MSG054 Rx from PLC: {}".format(str(total_54_rx)))
                report.log("\n-----------------------------------------------------------------------")

                break

        fd.close()
    except Exception as e:
        print (e.message)


def handle_Msg_56_log_file(fileName, report):
    print ("Handling a MSG 56 log file: " + fileName)
    try:
        fd = open(fileName, "r")
        lines = fd.readlines()

        for line in reversed(lines):
            search_str = "Rx ctr: "
            if (search_str in line):
                ptr = line.find(search_str)
                total_56_rx = int(line[ptr+len(search_str):len(line)])

                print ("Total MSG056 Rx from PLC: {}".format(str(total_56_rx)))

                report.log("Report - MSG056 RX from PLC")
                do_underline(report, "Report - MSG056 RX from PLC")
                report.log("Total MSG056 Rx from PLC: {}".format(str(total_56_rx)))
                report.log("\n-----------------------------------------------------------------------")

                break

        fd.close()
    except Exception as e:
        print (e.message)

def parse_ack_rx_log_file(fileName):
    print ("Handling an ack rx log file: " + fileName)
    total_data_msgs = 0
    try:
        fd = open(fileName, "r")
        lines = fd.readlines()

        for line in reversed(lines):
            search_str = ", Sending Data"
            if (search_str in line):
                ptr = line.find(search_str)
                ptrC = line.find(", ")
                total_data_tx = int(line[ptrC+len(", "):ptr].strip())

                print ("Total Data msgs Tx to PLC: {}".format(str(total_data_tx)))

                # report.log("\n-----------------------------------------------------------------------")
                # report.log("Report - Total Data msgs Tx to PLC")
                # report.log("Total Data msgs Tx to PLC: {}".format(str(total_data_tx)))
                # report.log("-----------------------------------------------------------------------")
                total_data_msgs = total_data_tx
                break

        fd.close()
    except Exception as e:
        print (e.message)

    return total_data_msgs


# -------- MAIN CODE ----------
if len(sys.argv) < 3:
    print ("Wrong no. of args passed. Correct usage: {} <{}> <{}>".format(sys.argv[0], "log folder path", "file timestamp"))
    sys.exit(-1)

log_dir = str(sys.argv[1])
timestamp = str(sys.argv[2])

report = util.CustomLogger(log_dest=util.LOG_DEST.FILE, fileName=log_dir + "/" + "Report_" + timestamp + ".txt")
handleFiles(log_dir=log_dir, timestamp=timestamp, report=report)
report.closeLogger()
