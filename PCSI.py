#import re
#import os
import numpy as np
import imageio
from pcsi.pcsiolw import PCSIolw
from PIL import ImageTk, Image
import cv2
#import serial
#from email.mime import base

import binascii
import bitstring
import argparse
from pcsi.pcsitximage_mmt import PCSItxImage
from pcsi.pcsidecoder_mmt import PCSIDecoder

def encode_callsign(callsign):
    base40_code = 0   
    for i in range(len(callsign)-1,-1,-1):
        base40_code *= 40
        if(ord(callsign[i]) >= ord('A') and ord(callsign[i]) <= ord('Z')):
            base40_code += ord(callsign[i]) - ord('A') + 14
        elif(ord(callsign[i]) >= ord('a') and ord(callsign[i]) <= ord('z')):
            base40_code += ord(callsign[i]) - ord('a') + 14
        elif(ord(callsign[i]) >= ord('0') and ord(callsign[i]) <= ord('9')):
            base40_code += ord(callsign[i]) - ord('0') + 1
    return base40_code

def decode_callsign(base40_code):
    callsign = ""   
    i = 0
    while(base40_code>0):
        i -= 1
        s = base40_code % 40
        if(s==0):
            callsign += '-'
        elif(s<11):
            callsign += chr(ord('0') + s - 1)
        elif(s<14):
            callsign += '-'
        else: callsign += chr(ord('A') + s - 14)
        base40_code = base40_code // 40
    return callsign

def encode_PCSI(inputfile,outputfile,imageID,callsign,bitDepth,chromaCompression):
    header = bitstring.pack(
        'uint:8, uint:8, uint:32',
        85,
        118,
        encode_callsign(callsign)).tobytes()

    txImage = PCSItxImage(inputfile,
                      imageID,
                      bitDepth,
                      chromaCompression,
                      infoBytes=218,
                      APRSprefixBytes=False,  # if we change this, we have to change the decode too
                      base91=False)
    
    for i in range(0,txImage.largestFullPacketNum+1):
        outputfile.write(header+txImage.genPayload(i)) 
    print("Wrote",txImage.largestFullPacketNum+1,"Packets")

def decode_PCSI(imageSelected, X, nynx, pixelsY, pixelsCbCr):
    Z = np.zeros(X.shape, dtype='uint8')
    ny = nynx[0]
    nx = nynx[1]
    XY = X[:,:,0]
    XCb = X[:,:,1]
    XCr = X[:,:,2]
    riY = pixelsY
    riCbCr = pixelsCbCr
    bY = XY.T.flat[riY].astype(float)
    bCb = XCb.T.flat[riCbCr].astype(float)
    bCr = XCr.T.flat[riCbCr].astype(float)
    # print([bY.shape, len(riY)])
    pcsiSolverY = PCSIolw(nx, ny, bY, riY)
    Z[:,:,0] = pcsiSolverY.go().astype('uint8')# choosenImage.get()
    pcsiSolverCb = PCSIolw(nx, ny, bCb, riCbCr)
    Z[:,:,1] = pcsiSolverCb.go().astype('uint8')# choosenImage.get()
    pcsiSolverCr = PCSIolw(nx, ny, bCr, riCbCr)
    Z[:,:,2] = pcsiSolverCr.go().astype('uint8')# choosenImage.get()
    Z=cv2.cvtColor(Z, cv2.COLOR_YCrCb2BGR)  # open CV switches order of channels, so this works
    imageio.imwrite(imageSelected, Z)

if __name__=="__main__":

    parser = argparse.ArgumentParser(description="Command line tool to PCSI",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-e", "--encode", action = 'store_true', default=False,
                        help = 'Encode image to PCSI packets.')
    parser.add_argument("-d", "--decode", action = 'store_true', default=False,
                        help = 'Decode PCSI packets to image.')    
    parser.add_argument("inputfile", type=str,
                        help="Input file name")
    parser.add_argument("-c", "--callsign", type=str, default='BJ1TG',
                        help="Set the callign. Accepts A-Z 0-9 and space, up to 6 characters.")
    parser.add_argument("-i", "--imageid", type=int, default=0,
                        help="Set the image ID (0-255).")
    parser.add_argument("-b", "--bitdepth", type=int, default=12,
                        help="Bit depth transmit (e.g., 24 for 24-bit color)")
    parser.add_argument("-C", "--chromacomp", type=int, default=20,
                        help="Chroma Compression ratio")
    parser.add_argument("outputfile", type=str,
                        help="Output file name")
    args = parser.parse_args()

if(args.encode and not args.decode):
    with open(str(args.outputfile), 'wb') as f:
        encode_PCSI(args.inputfile,f,args.imageid,args.callsign,args.bitdepth,args.chromacomp)
        f.close()

if(not args.encode and args.decode):
    decoder = PCSIDecoder()
    with open(str(args.inputfile), 'rb') as f:
        newdata = f.read()
        #print(newdata)
    if newdata:
        for imageSelected in decoder.Z:
            imageio.imwrite("pixel_raw_"+args.outputfile, decoder.Z[imageSelected])
        decoder.processSerial(newdata)
        for imageSelected in decoder.Z:

            decode_PCSI(args.outputfile,
                        decoder.Z[imageSelected][:],
                        decoder.nynx[imageSelected][:],
                        list(decoder.pixelsY[imageSelected]),
                        list(decoder.pixelsCbCr[imageSelected]))

    ny = decoder.nynx[imageSelected][0]
    nx = decoder.nynx[imageSelected][1]
    pixelsY = len(decoder.pixelsY[imageSelected])
    pixelsPerPacket = decoder.pixelsPerPacket[imageSelected]
    print("Callsign:", decode_callsign(decoder.callsign_Base40))
    print("ImageID:", decoder.imageID)
    print("Resolution:",str(nx)+"x"+str(ny))
    print("Total Packets", ((ny*nx)//pixelsPerPacket))
    print("Received Packets", (pixelsY//pixelsPerPacket))
        