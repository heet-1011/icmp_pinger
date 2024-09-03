from socket import *
import os
import sys
import struct
import time
import select
import binascii
import argparse

ICMP_ECHO_REQUEST = 8

def checksum(string):
    csum = 0
    countTo = (len(string) // 2) * 2
    count = 0

    while count < countTo:
        thisVal = string[count + 1] * 256 + string[count]
        csum += thisVal
        csum &= 0xffffffff
        count += 2

    if countTo < len(string):
        csum += string[len(string) - 1]
        csum &= 0xffffffff

    csum = (csum >> 16) + (csum & 0xffff)
    csum += (csum >> 16)
    answer = ~csum
    answer &= 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer

def receiveOnePing(mySocket, ID, timeout, destAddr):
    timeLeft = timeout
    while True:
        startedSelect = time.time()
        whatReady = select.select([mySocket], [], [], timeLeft)
        howLongInSelect = time.time() - startedSelect
        if whatReady[0] == []:
            return None
        timeReceived = time.time()
        recPacket, addr = mySocket.recvfrom(1024)
        howLongInSelect = time.time() - startedSelect
        timeReceived = time.time()

        icmpHeader = recPacket[20:28]
        type, code, recv_checksum, packetID, sequence = struct.unpack("bbHHh", icmpHeader)

        if packetID == ID and type == 0:
            bytesInDouble = struct.calcsize("d")
            timeSent = struct.unpack("d", recPacket[28:28 + bytesInDouble])[0]
            return (timeReceived - timeSent) * 1000
        elif type == 3:
            if code == 0:
                return "Destination Network Unreachable"
            elif code == 1:
                return "Destination Host Unreachable"
            elif code == 2:
                return "Destination Protocol Unreachable"
            elif code == 3:
                return "Destination Port Unreachable"
            elif code == 4:
                return "Fragmentation Needed and DF Flag Set"
            elif code == 5:
                return "Source Route Failed"
            else:
                return f"Destination Unreachable (Code {code})"
        elif type == 11:
            if code == 0:
            	return "TTL expired"
            elif code == 1:
            	return "Fragment Reassembly Time Exceeded"
            
        timeLeft -= howLongInSelect
        if timeLeft <= 0:
            return None

def sendOnePing(mySocket, destAddr, ID, ttl):
    mySocket.setsockopt(IPPROTO_IP, IP_TTL, ttl)

    myChecksum = 0
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    data = struct.pack("d", time.time())
    myChecksum = checksum(header + data)

    if sys.platform == 'darwin':
        myChecksum = htons(myChecksum) & 0xffff
    else:
        myChecksum = htons(myChecksum)

    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    packet = header + data
    
    try:
        mySocket.sendto(packet, (destAddr, 1))
    except OSError as e:
        print(f"Error sending packet: {e}")

def doOnePing(destAddr, timeout, ttl):
    icmp = getprotobyname("icmp")
    mySocket = socket(AF_INET, SOCK_RAW, icmp)
    myID = os.getpid() & 0xFFFF
    sendOnePing(mySocket, destAddr, myID, ttl)
    delay = receiveOnePing(mySocket, myID, timeout, destAddr)
    mySocket.close()
    return delay

def ping(host, timeout=1, count=4, ttl=64):
    dest = gethostbyname(host)
    print(f"Pinging {dest} using Python:")
    print("")
    
    rtt_list = []
    packets_sent = 0
    packets_received = 0

    for i in range(count):
        packets_sent += 1
        delay = doOnePing(dest, timeout, ttl)
        if isinstance(delay, str) or delay==None:
            print("Error : ", delay)
        else:
            rtt_list.append(delay)
            packets_received += 1
            print(f"Reply from {dest}: time={delay:.2f} ms")
        time.sleep(1)

    packet_loss = ((packets_sent - packets_received) / packets_sent) * 100
    min_rtt = min(rtt_list) if rtt_list else 0
    max_rtt = max(rtt_list) if rtt_list else 0
    avg_rtt = sum(rtt_list) / len(rtt_list) if rtt_list else 0

    print("\n--- {} ping statistics ---".format(host))
    print(f"{packets_sent} packets transmitted, {packets_received} received, {packet_loss:.1f}% packet loss")
    print(f"rtt min/avg/max = {min_rtt:.2f}/{avg_rtt:.2f}/{max_rtt:.2f} ms")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="icmp pinger arguments")
    parser.add_argument("-d", type=str, help="Destination Address (ip or Domain)")
    parser.add_argument("-c", type=int, help="No of ping", default=5)
    parser.add_argument("-t", type=int, help="Time to live", default=64)    
    args = parser.parse_args()
    if args.d is None:
    	print("Add destination address or domain name using -d")
    	sys.exit(0)        
    
    ping(args.d, timeout=1, count=args.c, ttl=args.t)

