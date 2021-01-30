import matplotlib.pyplot as plt
from matplotlib import style
import numpy as np

style.use("fivethirtyeight")

fd = open ("./logs/hq_plc_testing/5_Aug_2020/own_vm_testing/client_log_20200805__082354_616.txt", "r")
log_lines = fd.readlines()
fd.close()

size_arr = []
pen_ack_arr = []

# array to plot
xs = []
ys = []

rx_data_str = "Receiving data: "
pending_ack_str = "Pending ack to match: "

for line in log_lines:
    res = line.find(rx_data_str)
    if (res != -1):
        res1 = line.find(" bytes")
        size = line[(res+len(rx_data_str)):res1]
        size_arr.append(int(size))
        # print (size)
        # plt.title("Received Data Size - Overall")
        # plt.xlabel("Messages Count")
        # plt.ylabel("Data Size")
        # x = [i for i in range(len(size_arr))]
        # xs = np.array(x, dtype=int)
        # ys = np.array(size_arr, dtype=int)
    else:
        pen_ack_f = line.find(pending_ack_str)
        if (pen_ack_f != -1):
            pen_ack_count = int(line[(pen_ack_f+len(pending_ack_str)):len(line)])
            pen_ack_arr.append(pen_ack_count)
            # print (pen_ack_count)
            plt.title("Pending Ack to Match Count")
            plt.xlabel("Messages Count")
            plt.ylabel("Pending Ack Count")
            x = [i for i in range(len(pen_ack_arr))]
            xs = np.array(x, dtype=int)
            ys = np.array(pen_ack_arr, dtype=int)


#plt.scatter(xs, ys, s=10, color='r')
plt.plot(xs, ys, color="r")
plt.show()



