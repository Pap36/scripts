# first read the contents of meshsampledata.txt file and store it in a list
# for each line append in the beginning the type bytearray according to the type of data
# and also append the length of the data
# then write the contents of the list to formattedmeshsampledata.txt file

import os
import sys
import struct

meshDataType = {
    "prov": "29",
    "mesh": "2A",
    "unpbeacon": "2B00",
    "snbeacon": "2B01",
    "prbeacon": "2B02",
}

# read the contents of meshsampledata.txt file and store it in a list
def read_meshsampledata():
    meshsampledata = []
    with open('meshsampledata.txt', 'r') as f:
        for line in f:
            meshsampledata.append(line.strip())
    return meshsampledata

# for each line append in the beginning the type bytearray according to the type of data
# and also append the length of the data before that
# the format of each line is meshDataType: hexValue: SPEC Reference
# the format of each formatted line is: lengthOfHexAsHex (padded with 0 if necessary) + meshDataType + hexValue
def format_meshsampledata(meshsampledata):
    formattedmeshsampledata = []
    for line in meshsampledata:
        # for each line append the following string lengthAsHex (without mesh type) + meshDataType + line(without mesh type)
        # the length must always be even length
        # if the length of the line is odd, then pad it with 0 in the beginning

        # get the mesh type
        meshType = line.split(':')[0].strip()
        # get the hex value
        hexValue = line.split(':')[1].strip()
        # get the SPEC Reference
        specRef = line.split(':')[2].strip()
        # get the length of the meshDataType + hexValue
        length = len(meshDataType[meshType] + hexValue) // 2
        # convert the length to hex
        lengthAsHex = hex(length)[2:].upper()
        # if the length is odd, then pad it with 0 in the beginning
        if len(lengthAsHex) % 2 != 0:
            lengthAsHex = '0' + lengthAsHex
        # append the lengthAsHex + meshDataType + hexValue -- // Refer to Sample Data specRef
        formattedmeshsampledata.append('"' + lengthAsHex + meshDataType[meshType] + hexValue.upper() + '".decodeHex(), // Refer to Sample Data ' + specRef)

        
    return formattedmeshsampledata

# write the contents of the list to formattedmeshsampledata.txt file
def write_formattedmeshsampledata(formattedmeshsampledata):
    with open('formattedmeshsampledata.txt', 'w') as f:
        for line in formattedmeshsampledata:
            f.write(line + '\n')

def main():
    meshsampledata = read_meshsampledata()
    formattedmeshsampledata = format_meshsampledata(meshsampledata)
    write_formattedmeshsampledata(formattedmeshsampledata)

if __name__ == '__main__':
    main()