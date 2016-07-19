# Name: RenameStills.py
#
# Based on work by
# Author: Brian Klug (@nerdtalker / brian@brianklug.org)
#https://gist.github.com/nerdtalker/4187084

# Purpose:
#Rename jpg & ARW's as yyyy-mm-dd-hh-mm-ss-#### where #### is the existing sequence no
# using EXIF data

# library for the EXIF data
try:
    import exifread
except:
    print ("exifread was not found in the same directory as exifmover.py")


import traceback
import os
import time
import tkinter as tk
from tkinter import filedialog

import re
from operator import attrgetter

# only handle known types
includedTypes = [ "JPG" , "jpg" , "ARW" , "arw" , "CR2" , "cr2" , "TIF" , "tif" ]


#class for managing sequences of images in the same second
class processedName():
    def __init__(self,origName= "",dateTime= "",seq= -1,type= ""):
        self.origName = origName
        self.dateTime = dateTime    #exif date-time
        self.origSeq = seq              # embedded seq in the file
        self.type = type            # type ([-3:]
        self.seq = -1                # a consecutive number for multiple shots in one second. -1 means no sequence found
        self.newName = ""           #where we will put the new name

    def __str__(self):
        return str( self.origName) + '\t' + str(self.dateTime)  + '\t'+ str(self.origSeq)  + \
               '\t' + str(self.type) + '\tseq:' + str(self.seq)+ '\tnN:' + str(self.newName)

def createSequencedNames(dirName):
    '''
        creates date&time filenames, with seq numbers for duplicates
        :param dirName: directory to parse
        :return: a list of processedName objects with correctly sequenced names
    '''

    dirList=os.listdir(dirName)
    print('%3d files found to process' % len(dirList))

    # a list of processedNames
    newNames = []

    for origName in dirList:
        # set full name and extract type (no path)
        p = processedName(origName,"",0,origName[origName.rfind('.')+1:])
        if p.type in includedTypes:  #only try to get date from EXIF compliant files
            p.dateTime = getEXIFTime(dirName + '/'+ origName)
            # try to grab a sequence number from the file NAME
            try:
                p.origSeq = int(re.findall(r'\d+',origName)[0])
            except:
                p.origSeq = 0
        newNames.append(p)

    #find sequences in same file types
    prevDateTime = ""  # dateTime is always set, thus this will work for 1st iteration.
    prevType = ""
    seqTrack = 0

    #sort by type to find same-second sequences
    newNames.sort(key = attrgetter('type', 'origSeq'))

    # uses indexing to deal with the 'previous' element in a sequence
    for i in range(len(newNames)):
        if newNames[i].dateTime == prevDateTime and newNames[i].type == prevType:
            if seqTrack == 0: # on the first one of a seq, go back and fix the previous
                newNames[i-1].seq = seqTrack
                seqTrack += 1
            newNames[i].seq = seqTrack
            seqTrack += 1
        else:
            seqTrack = 0

        prevDateTime = newNames[i].dateTime
        prevType = newNames[i].type

    #sequencing sorted, now build the file names
    for n in newNames:
        if n.type in includedTypes:
            if n.seq != -1:
                n.newName = n.dateTime + "-%02d" % n.seq + '.'+ n.type
            else:
                n.newName = n.dateTime + '.'+ n.type
        else:
            n.newName = n.origName
    return newNames

def getModTime(fileName):
    # get the file MODIFIED time

    statbuf = os.stat(fileName)
    dateTime = time.localtime((statbuf.st_mtime))

    # Format it as yyyy-mm-dd-hh-mm-ss
    return "%04d-%02d-%02d %02d-%02d-%02d" % (dateTime[0], dateTime[1], dateTime[2],
            dateTime[3], dateTime[4], dateTime[5])

def getEXIFTime(fileName):
    # get the image time based on EXIF metadata, esle use mod time
    newName = ""
    f = open(fileName,'rb')
    try:
        # tags = exifread.process_file(f)
        tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal', details=False)
        # tags = exifread.process_file(f,stop_tag='EXIF DateTime')
        # print(tags['EXIF DateTimeOriginal'])
    except:
        # the error will be caught in the tag processing
        pass

    try:
        # get the exif version date time
        EXIFDateTime = str(tags['EXIF DateTimeOriginal'])
        # print("EXIFDateTime ="+EXIFDateTime)
        #exclude filetype
        newName = EXIFDateTime.replace(':','-') #+"."+fileName[-3:]
    except:
        # else use the file modified date (Creation gets changed on copy)
        print ("Couldn't read EXIF date on " + fileName + "\nUsing mod time")
        # exclude filetype
        newName = getModTime(fileName) # + "."+fileName[-3:]

    f.close()

    return newName

def renameStillsFolderOLD(dirName):
    """
    Rename all the still image files in dirName to yyyy-mm-dd-hh-mm-ss-## where ## is a sequence num.
    Handle interleaved JPG/ ARW and pre-existing files in the folder
    """

    '''
        should be re-runable - if newname = oldname, happily do nothing
        dealing with dup times
        sort
        handle duplicates on HDD during rename
    '''

    dirList=os.listdir(dirName)

    # track the previous file, for multiple files in the same second
    prevFile = ""
    # a counter to handle multiple images in the same second
    multiSeq = 1

    errorCount = 0

    for shortName in dirList:
        fname = dirName + '/' + shortName
        newName = ""

        if os.path.isfile(fname):
            if fname[-3:] in includedTypes:
                #print ("File name is " + fname)
                try:
                    newName = dirName + '/' + getEXIFTime(fname)

                    #if os.path.exists(newName):
                    # check for multiple images from source.
                    # or  duplicates already in dest
                    ########################### fix this logic - not sequencing cleanly with jpg & arw at the same time
                    if (newName == prevFile) or (os.path.exists(newName)) :
                        prevFile = newName #before seq added. Will stay the same until the second changes``
                        newName = newName[:-4] + "-%02d" % multiSeq + newName[-4:]
                        # if newName != prevFile: #pre-existing dup
                        #     multiSeq = 1
                        # else:
                        multiSeq += 1  #we have a run of images in the same second
                    else:
                        multiSeq = 1 # date/name change => reset sequence counter
                    #print("Rename " + fname[-25:] + " to "+ newName[-25:])
                    os.rename(fname,newName)

                except Exception as e:
                    errorCount += 1
                    print ("Oh no. Rename " + fname + " failed")
                    print(traceback.format_exc())

    if errorCount : print("There were %2d errors",errorCount)
    return errorCount

def renameStillsFolder(dirName,newNameList):
    """
    Rename all the still image files in dirName to yyyy-mm-dd-hh-mm-ss-## where ## is a sequence num.
    Use the names in
    :param dirName - string with the fully qualified path to the files
    :param newNameList - list of processedName objects, ready to be applied to HDD
    """

    errorCount = 0

    #for shortName in dirList:
    for n in newNameList:
        fname = dirName + '/' + n.origName

        if os.path.isfile(fname):
            if n.type in includedTypes:
                #print ("File name is " + fname)
                try:
                    newName = dirName + '/' + n.newName
                    #
                    # print("Rename " + fname[-30:] + " to "+ newName[-30:])
                    print('.',end='')
                    os.rename(fname,newName)

                except Exception as e:
                    errorCount += 1
                    print ("Oh no. Rename " + fname + " failed")
                    print(traceback.format_exc())

    print()
    if errorCount : print("There were %2d errors" % errorCount)
    return errorCount

def main():

    # for testing with just one file
    # fileName =filedialog.askopenfilename(
    #         title = "Media file to query:",
    #         initialdir = "C:/Users/grant/Documents/scratch/sonySDStructure"
    #         )
    #
    #
    # if fileName != "" :
    #     print('\n'+fileName + ' becomes ' + getEXIFTime(fileName))

    #close the root window
    root = tk.Tk()
    root.withdraw()

    stillsPath = filedialog.askdirectory(
                title = "Directory in which to rename jpg & ARW & CR2 & Tif files ",
                initialdir = "C:/Users/grant/Documents/scratch/sonySDStructure/DCIM/10060708"
                )

    print(stillsPath)
    # Exit on cancel!
    if stillsPath == "" : return

    start_time=time.time()

    #renameStillsFolder(stillsPath)
    newNames = createSequencedNames(stillsPath)
    renameStillsFolder(stillsPath,newNames)

    # Double check what happens to sequence numbers on renaming renamed files. Seems to be dependent on natural order?
    # maybe sort by EXIF date if seq is the same for the whole folder (since it defaults to year in this case)

    print ('Done. Execution took {:0.3f} seconds'.format((time.time() - start_time)))

    # for n in newNames:
    #     print(n)

if __name__ == '__main__':
    main()