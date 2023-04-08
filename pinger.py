from socket import *
import os
import sys
import struct
import time
import select
import pandas as pd

ICMP_ECHO_REQUEST = 8

def checksum(string):
    csum = 0
    countTo = (len(string) // 2) * 2
    count = 0

    while count < countTo:
        thisVal = (string[count + 1]) * 256 + (string[count])
        csum += thisVal
        csum &= 0xffffffff
        count += 2

    if countTo < len(string):
        csum += (string[len(string) - 1])
        csum &= 0xffffffff

    csum = (csum >> 16) + (csum & 0xffff)
    csum = csum + (csum >> 16)
    answer = ~csum
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer

def receiveOnePing(mySocket, ID, timeout, destAddr):
    timeLeft = timeout

    while 1:
        startedSelect = time.time()
        whatReady = select.select([mySocket], [], [], timeLeft)
        howLongInSelect = (time.time() - startedSelect)
        if whatReady[0] == []:  # Timeout
            return "Request timed out.", None

        timeReceived = time.time()
        recPacket, addr = mySocket.recvfrom(1024)

        # Fetch the IP header from the packet
        ipHeader = recPacket[:20]
        _, _, _, _, _, _, ttl, _, _, _, _ = struct.unpack("!BBHHHBBHII", ipHeader)

        # Fetch the ICMP header from the IP packet
        icmpHeader = recPacket[20:28]
        icmpType, code, mychecksum, packetID, sequence = struct.unpack("bbHHh", icmpHeader)

        if icmpType != 8 and packetID == ID:
            bytesInDouble = struct.calcsize("d")
            timeSent = struct.unpack("d", recPacket[28:28 + bytesInDouble])[0]
            return timeReceived - timeSent, ttl

        timeLeft = timeLeft - howLongInSelect
        if timeLeft <= 0:
            return "Request timed out.", None

def sendOnePing(mySocket, destAddr, ID):
    # Header is type (8), code (8), checksum (16), id (16), sequence (16)

    myChecksum = 0
    # Make a dummy header with a 0 checksum
    # struct -- Interpret strings as packed binary data
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    data = struct.pack("d", time.time())
    # Calculate the checksum on the data and the dummy header.
    myChecksum = checksum(header + data)

    # Get the right checksum, and put in the header

    if sys.platform == 'darwin':
        # Convert 16-bit integers from host to network byte order
        myChecksum = htons(myChecksum) & 0xffff
    else:
        myChecksum = htons(myChecksum)

    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    packet = header + data

    mySocket.sendto(packet, (destAddr, 1))  # AF_INET address must be tuple, not str

def doOnePing(destAddr, timeout):
    icmp = getprotobyname("icmp")

    # SOCK_RAW is a powerful socket type. For more details: https://sock-raw.org/papers/sock_raw
    mySocket = socket(AF_INET, SOCK_RAW, icmp)

    myID = os.getpid() & 0xFFFF  # Return the current process i
    sendOnePing(mySocket, destAddr, myID)
    delay, ttl = receiveOnePing(mySocket, myID, timeout, destAddr)
    mySocket.close()
    return delay, ttl

def ping(host, timeout=1):
    # timeout=1 means: If one second goes by without a reply from the server,  
    # the client assumes that either the client's ping or the server's pong is lost
    dest = gethostbyname(host)
    print("\nPinging " + dest + " using Python:")
    print("")

    response = pd.DataFrame(columns=['bytes', 'rtt', 'ttl'])

    # Send ping requests to a server separated by approximately one second
    for i in range(0, 4):
        delay, ttl = doOnePing(dest, timeout)
        if delay is None or ttl is None:
            print("Request timed out.")
        else:
            response = response.append({'bytes': 8, 'rtt': delay * 1000, 'ttl': ttl}, ignore_index=True)
            print("Received {} bytes, rtt = {:.6f} ms, ttl = {}".format(8, delay * 1000, ttl))
        time.sleep(1)  # wait one second

    packet_lost = 0
    packet_recv = 0

    for index, row in response.iterrows():
        if row['rtt'] == 0:
            packet_lost += 1
        else:
            packet_recv += 1

    print("--- {} ping statistics ---".format(host))
    print("{0:1d} packets transmitted, {1:1d} packets received, {2:.1f}% packet loss".format(packet_lost + packet_recv, packet_recv, packet_lost / (packet_lost + packet_recv) * 100))

    packet_min = 0
    packet_avg = 0.0
    packet_max = 0
    stdev = 0

    if packet_recv > 0:
        packet_min = round(response['rtt'].min(), 2)
        packet_max = round(response['rtt'].max(), 2)
        packet_avg = round(response['rtt'].mean(), 2)
        stdev = round(response['rtt'].std(), 2)

    vars = pd.DataFrame(columns=['min', 'avg', 'max', 'stddev'])
    vars = vars.append({'min': str(packet_min), 'avg': str(packet_avg), 'max': str(packet_max), 'stddev': str(stdev)}, ignore_index=True)
    print(vars)
    return vars

if __name__ == '__main__':
    ping("google.com")
    ping("nyu.edu")
