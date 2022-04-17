#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 11 23:59:08 2020



@author: showard
"""

import numpy as np
# import math  # used for log functions
from bitstring import BitStream  # maybe use "Bits" instead of "BitStream"?
from pcsi.prandom import shufflePixels
from pcsi.base91 import isBase91, base91tobytes

# eventually will need some kind of "router" where you:
class PCSIDecoder():
    def __init__(self):
        # self.Z = np.zeros([2,2], dtype='uint8')
        self.Z = {}
        self.serialBuffer = b''
        self.pixelsY = {}
        self.pixelsCbCr = {}
        self.nynx = {}
        self.destFilter = ""
        self.pixelsPerPacket = {}
        # self.uninit=1
    def processSerial(self, rawSerial):
        """
        first collect bits from serial in to a BitStream buffer. Then split at 0xC0
        you now have a list of buffers. Discard garbage ones, and keep the last one
        to accumulate more bits in to as they come in. Don't process that last one,
        it might still have stuff in it - save it until the next time through. Pass
        good packets to unkissify
        """
        self.Buffer = ""
        rawSerial = BitStream(rawSerial)
        # print(rawSerial)
        raw = [s for s in rawSerial.split('0x5576', bytealigned = True)]
        #print(raw)

        for packet in raw[1:-1]:  # skip the stuff before the first '0xc0'
            packet = self.Buffer + packet
            if len(packet) >= 1784:
                self.Buffer = ""
                packet.read('uint:8')
                packet.read('uint:8')
                packet.read('uint:32')
                imageID = packet.read('uint:8')
                packetNum = packet.read('uint:16')
                ny= packet.read('uint:8')*16
                nx= packet.read('uint:8')*16
                numYCbCr = packet.read('uint:8')
                channelBD = packet.read('uint:8')+1
                #print([controlField, PIDField, imageID, ny, nx, packetNum, numYCbCr, channelBD])
                hashID = str(imageID)
                # print(hashID)
                pixelYData = []
                pixelCbData = []
                pixelCrData = []
                for tmp in range(numYCbCr):
                    pixelYData.append(packet.read( 'uint:' + str(channelBD)))
                    pixelCbData.append(packet.read( 'uint:' + str(channelBD)))
                    pixelCrData.append(packet.read( 'uint:' + str(channelBD)))
                while packet.len - packet.pos >= channelBD:
                    pixelYData.append(packet.read( 'uint:' + str(channelBD)))

                pixelList = shufflePixels(ny,nx)
                startingPixel = packetNum * (len(pixelYData))  # last packet might have fewer!
                pixelID = pixelList[startingPixel:startingPixel+len(pixelYData)]

                # temporarily display and hold image data
                # pixels are counted down a column first, so we transpose image
                # this conversion is "wrong," need to do it as floats

                #print(pixelID)
                #print(pixelYData)
                pixelYData = np.array(pixelYData) / (2**(channelBD)-1) * (2**8-1)
                pixelYData[pixelYData>255]=255

                pixelCbData = np.array(pixelCbData) / (2**(channelBD)-1) * (2**8-1)
                pixelCbData[pixelCbData>255]=255

                pixelCrData = np.array(pixelCrData) / (2**(channelBD)-1) * (2**8-1)
                pixelCrData[pixelCrData>255]=255

                if hashID not in self.Z:
                    self.Z[hashID] = np.zeros((ny,nx,3), dtype='uint8')
                    self.pixelsY[hashID] = set()
                    self.pixelsCbCr[hashID] = set()
                    self.nynx[hashID] = (ny,nx)
                    self.pixelsPerPacket[hashID] = len(pixelYData)
                self.Z[hashID][:,:,0].T.flat[pixelID] = np.around(pixelYData)
                # self.Z[:,:,0].T.flat[pixelID] <<= (8-channelBD)
                self.Z[hashID][:,:,1].T.flat[pixelID[:len(pixelCbData)]] = np.around(pixelCbData)
                # self.Z[:,:,1].T.flat[pixelID] <<= (8-channelBD)
                self.Z[hashID][:,:,2].T.flat[pixelID[:len(pixelCrData)]] = np.around(pixelCrData)
                # self.Z[:,:,2].T.flat[pixelID] <<= (8-channelBD)
                # self.Z = self.Z << (8-channelBD)  # (Z >> (8-channelBD) ) << (8-channelBD) # /(2**channelBD-1)*255
                # self.Z = ycbcr2rgb(self.Z.astype(float))
                self.pixelsY[hashID].update(pixelID)
                self.pixelsCbCr[hashID].update(pixelID[:len(pixelCrData)])
        self.Buffer =  packet