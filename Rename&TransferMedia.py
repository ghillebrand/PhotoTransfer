# Name: RenameVideo.py
#
# file traversal was based on work by
# Author: Brian Klug (@nerdtalker / brian@brianklug.org)
#https://gist.github.com/nerdtalker/4187084

# Purpose:
#Rename still images as yyyy-mm-dd-hh-mm-ss-#### where #### is the existing sequence no
# using EXIF data
#
# rename movie files to V##_start date & time, using the MediaInfo library
# Also flags non-25FPS video (Useful for Lightworks editing!)
#

# specialised, non-standard lib imports:
# library for the stills EXIF data
try:
    import exifread
except:
    print ("exifread was not found in the same directory as this program")
    #Todo: Exit code 101 => Exifread not found
    exit(101)

# for video metadata
try:
    from MediaInfoDLL3 import *
except :
    print ("MediaInfo library not found in the same directory as this program\n Video wont work")
    #Currently MI only works with a 64bit Python
    # die without media info
    # TODO: be more elegant - spew a URL?
    # Todo: Exit code 102 => MediaInfo not found
    exit(102)

# standard Python imports
import traceback
import os
import time
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog
import shutil
import re
from operator import attrgetter

# only handle known types
# TODO: Sort out casing
INCLUDED_STILL_TYPES = [ "JPG" , "jpg" , "ARW" , "arw" , "CR2" , "cr2" , "TIF" , "tif" ]

INCLUDED_VIDEO_TYPES = ["MOV", "mov", "MP4", "mp4", "MTS", "mts"]

# conversion from UTC to SAST
UTC_SECONDS = 2*3600

# class for collecting copy errors
class CTError(Exception):
    def __init__(self, errors):
        self.errors = errors

#class for managing sequences of images in the same second
class processedName():
    def __init__(self,origName= "",dateTime= "",seq= -1,type= ""):
        self.origName = origName
        self.dateTime = dateTime    #exif date-time
        self.origSeq = seq          # embedded seq in the file
        self.type = type            # file type origName[origName.rfind('.')+1:]
        self.seq = -1                # a consecutive number for multiple shots in one second. -1 means no sequence found
        self.newName = ""           #where we will put the new name

    def __str__(self):
        return str( self.origName) + '\t' + str(self.dateTime)  + '\t'+ str(self.origSeq)  + \
               '\t' + str(self.type) + '\tseq:' + str(self.seq)+ '\tnN:' + str(self.newName)

#class for managing sequences of images in the same second
# design itteration from processedName, with adds for renaming.
class mediaItem():
    def __init__(self,origPath = "",origName= "",StillVideo = "",fileType= ""):
        '''
            setup a new mediaItem instance.
            Only sets srcname stuff here - no additional calls to OS or file opening (delays!) here
        '''
        self.origPath = origPath
        self.origName = origName
        if fileType != "":              # file type origName[origName.rfind('.')+1:]
            self.fileType = fileType    #explicitly set
        else:                           #extract it
            self.fileType = origName[origName.rfind('.')+1:]

        self.dateTime = datetime(1,1,1)              #Metadata (exif) date-time - as a pure date for sorting & processing
        # is this still or video media type ('S' or 'V']
        if self.fileType in INCLUDED_STILL_TYPES:
            self.StillVideo = 'S'
        elif self.fileType in INCLUDED_VIDEO_TYPES:
            self.StillVideo = 'V'
        else:
            self.StillVideo = 'U'   # unknown for now

        self.size = 0                   # size on disk (nice for updating progress)
        # try to grab a sequence number from the file NAME (takes the first contiguous number string)
        try:
            self.origSeq = int(re.findall(r'\d+',origName)[0])
        except:
            self.origSeq = 0

        self.seq = -1                   # a consecutive number for multiple shots in one second. -1 means no sequence found
        self.newPath = ""               # path for new name
        self.newName = ""               #where we will put the new name
        self.namePrefix = ""            # a place to handle special name prefixes (eg vid seq)
        self.nameSuffix = ""            # a place to handle special name suffices (eg 24FPS)

    def __str__(self):
        return str( self.origPath) + '$' + str( self.origName) + '\n   dt:' + str(self.dateTime)  + '\t SVU:' + \
            str(self.StillVideo) + '\t' + str(self.size) + 'B \t oSeq:' + str(self.origSeq) + \
            '\t fileType<' + str(self.fileType) + '>\tseq:' + str(self.seq)+ \
            '\n new Path:' + str(self.newPath) + '\t newN:' + str(self.newName)

    def updateMediaTags(self):
        ''' open the file via os, mediaInfo or exifread to get tags
            Based on getModTime() and getEXIFTime() ideas
            Sets newName to its default value
            Sets dateTime,and FPS check for Vid
        '''

        if self.StillVideo == 'S':
            # use exif data
            f = open(self.origPath+self.origName,'rb')
            try:
                tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal', details=False)
                # print(tags['EXIF DateTimeOriginal'])
            except:
                # the error will be caught in the tag processing
                pass

            try:
                # get the exif version date time
                EXIFDateTime = str(tags['EXIF DateTimeOriginal'])
                # print("EXIFDateTime ="+EXIFDateTime)
                self.newName = EXIFDateTime.replace(':','-')
            except:
                # else use the file modified date (Creation gets changed on copy)
                print ("Couldn't read EXIF date on " + self.origPath+self.origName + "\nUsing mod time")
                self.newName = getModTime(self.origPath+self.origName)

            self.dateTime = datetime.strptime(self.newName, "%Y-%m-%d %H-%M-%S")
            f.close()

        elif self.StillVideo == 'V':
            # use MediaInfo
            MI = MediaInfo()
            MI.Open(self.origPath+self.origName)
            # print("Info for ", srcname)

            encodedDate = MI.Get(Stream.General, 0, "Encoded_Date")

            # HACK! MI ALWAYS includes "UTC" on encoded time, even if it's actually local :(
            # Also remove the "20" since it takes space on the timeline/ bin  in LWKS
            if encodedDate != "" :
                # encodedDate = encodedDate[6:]
                self.dateTime = datetime.strptime(encodedDate, "%Z %Y-%m-%d %H:%M:%S")
                encodedDate = self.dateTime.strftime("%y-%m-%d %H-%M-%S")
            # MTS files don't have encodeDate, hack it from OS File Mod date minus duration                                     ]
            if encodedDate == "":
                # this uses the datetime library, which handles all the midnight/ end of month type issues
                # https://docs.python.org/3/library/datetime.html
                fileModDate = MI.Get(Stream.General, 0, "File_Modified_Date")
                #convert this to a datetime format
                fDT = datetime.strptime(fileModDate, "%Z %Y-%m-%d %H:%M:%S.%f")

                # convert the duration from millseonds to a datetime object
                fileDuration = timedelta(0, float( MI.Get(Stream.General, 0, "Duration") )/1000 )

                # print("Mod:  " + fileModDate + " duration (s) " + str(fileDuration))
                # reverse back to the start time of the clip, and correct for TImezone
                self.dateTime = fDT - fileDuration + timedelta(0,UTC_SECONDS)
                # print ("new encoded time: " + str(datetime.timedelta(seconds=startSecsFromMidnight)))

                encodedDate = self.dateTime.strftime("%y-%m-%d %H-%M-%S")

            self.newName = encodedDate
            # print("new encoded time: " + encodedDate)

            # To track non-25fps movies for later transcoding
            # embed a "-##FPS" before the filetype for non-25FPS files
            # print("FrameRate :",MI.Get(Stream.General, 0, "FrameRate"))
            FPS = float(MI.Get(Stream.General, 0, "FrameRate"))
            if FPS != 25:
                self.nameSuffix += "_%dFPS"%FPS

            MI.Close()

    def getDate(self):
        """ return the YYYY_MM_DD a file was created """
        return self.dateTime.strftime("%Y_%m_%d")

def createSequencedNames(dirName):
    '''
        creates date&time srcnames, with seq numbers for duplicates
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
        if p.type in INCLUDED_STILL_TYPES:  #only try to get date from EXIF compliant files
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
        if n.type in INCLUDED_STILL_TYPES:
            if n.seq != -1:
                n.newName = n.dateTime + "-%02d" % n.seq + '.'+ n.type
            else:
                n.newName = n.dateTime + '.'+ n.type
        else:
            n.newName = n.origName
    return newNames

def getModTime(srcname):
    # get the file MODIFIED time

    statbuf = os.stat(srcname)
    dateTime = time.localtime((statbuf.st_mtime))

    # Format it as yyyy-mm-dd-hh-mm-ss
    return "%04d-%02d-%02d %02d-%02d-%02d" % (dateTime[0], dateTime[1], dateTime[2],
            dateTime[3], dateTime[4], dateTime[5])

def getEXIFTime(srcname):
    # get the image time based on EXIF metadata, esle use mod time
    newName = ""
    f = open(srcname,'rb')
    try:
        # tags = exifread.process_file(f)
        tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal')
        # tags = exifread.process_file(f,stop_tag='EXIF DateTime')
        # print(tags['EXIF DateTimeOriginal'])
    except:
        # the error will be caught in the tag processing
        pass

    try:
        # get the exif version date time
        EXIFDateTime = str(tags['EXIF DateTimeOriginal'])
        # print("EXIFDateTime ="+EXIFDateTime)
        newName = EXIFDateTime.replace(':','-')
    except:
        # else use the file modified date (Creation gets changed on copy)
        print ("Couldn't read EXIF date on " + srcname + "\nUsing mod time")
        newName = getModTime(srcname)

    f.close()

    return newName

def get_sec(s):
    '''
    http://stackoverflow.com/questions/6402812/how-to-convert-an-hmmss-time-string-to-seconds-in-python
    modified to deal with millisecs in file names
    '''
    l = s.split(':')
    return int(l[0]) * 3600 + int(l[1]) * 60 + float(l[2])

def getMItime(srcname):
    ''' get the file (start?) time
    :param video file name
    :return: the time in yy-mm-dd hh-mm-ss format, no filetype
        uses the MediaInfo Library
        MediaInfo.Dll - http://MediaArea.net/MediaInfo
        https://mediaarea.net/en/MediaInfo/Download/Windows
        to get date & time & rates
        mediainfo.dll & py mus tbe in the same dir
    '''

    MI = MediaInfo()
    MI.Open(srcname)
    # print("Info for ", srcname)

    # To track non-25fps movies for later transcoding
    # embed a "-##FPS" before the filetype for non-25FPS files
    # print("FrameRate :",MI.Get(Stream.General, 0, "FrameRate"))
    FPS = float(MI.Get(Stream.General, 0, "FrameRate"))
    if FPS == 25:
        FPSMod = ""
    else:
        FPSMod = "_%dFPS"%FPS

    encodedDate = MI.Get(Stream.General, 0, "Encoded_Date")
    # TODO: Proper datetime restructure, since MI returns colons in time!!

    # HACK! MI ALWAYS includes "UTC" on encoded time, even if it's actually local :(
    # Also remove the "20" since it takes space on the timeline/ bin  in LWKS
    if encodedDate != "" :
        # encodedDate = encodedDate[6:]
         encodedDate = datetime.strptime(encodedDate, "%Z %Y-%m-%d %H:%M:%S").strftime("%y-%m-%d %H-%M-%S")
    # MTS files don't have encodeDate, hack it from OS File Mod date minus duration                                     ]
    if encodedDate == "":
        # this uses the datetime library, which handles all the midnight/ end of month type issues
        # https://docs.python.org/3/library/datetime.html
        fileModDate = MI.Get(Stream.General, 0, "File_Modified_Date")
        #convert this to a datetime format
        fDT = datetime.strptime(fileModDate, "%Z %Y-%m-%d %H:%M:%S.%f")

        # convert the duration from millseonds to a datetime object
        fileDuration = timedelta(0, float( MI.Get(Stream.General, 0, "Duration") )/1000 )

        # print("Mod:  " + fileModDate + " duration (s) " + str(fileDuration))
        # reverse back to the start time of the clip, and correct for TImezone
        newDT = fDT - fileDuration + timedelta(0,UTC_SECONDS)
        # print ("new encoded time: " + str(datetime.timedelta(seconds=startSecsFromMidnight)))

        encodedDate = newDT.strftime("%y-%m-%d %H-%M-%S")

    # add back the non-standard FPS indicator - blank for 25 FPS, non blank otherwise
    # This should be a mediaItem modifier
    encodedDate += FPSMod
    # print("new encoded time: " + encodedDate)

    MI.Close()

    return encodedDate

def renameVideoFolder(dirName):
    """
    Rename all the Video image files in dirName to M####-yy-mm-dd-hh-mm-sswhere #### is a sequence num.
    :returns number of files written
    """
    '''
        should be re-runable - if newname = oldname, happily do nothing
        sort
        handle duplicates on HDD during rename
    '''

    dirList=os.listdir(dirName)

    errorCount = 0
    # a sequence counter for aiding NLE timeline clip ID
    seqCount = 0

    for shortName in dirList:
        fname = dirName + '/' + shortName
        # print ("File name is " + fname)
        if os.path.isfile(fname):
            if fname[fname.rfind('.')+1:] in INCLUDED_VIDEO_TYPES:
                #print ("File name is " + fname)
                try:
                    # note the prepended "V%d" MAY cause sort-by-name to not equal sort by mod date??? May need to sort the names first???
                    # solved in copy version (using mediaItem class) by having a proper prefix field
                    newName = dirName + '/' + "V%d_" % seqCount + getMItime(fname) + '.'+fname[fname.rfind('.')+1:]
                    seqCount += 1
                    # TODO: if the file exists, this is an error (for now)  Check about re-runs, etc
                    # if not os.path.exists(newName):
                    # print("Rename " + fname[-30:] + " to "+ newName[-30:])
                    print('.',end='')
                    os.rename(fname,newName)

                except Exception as e:
                    errorCount += 1
                    print ("Oh no. Rename " + fname + " failed")
                    print(traceback.format_exc())

    if errorCount : print("There were %2d errors" % errorCount)
    return seqCount

def renameStillsFolder(dirName,newNameList):
    """
    Rename all the still image files in dirName to yyyy-mm-dd-hh-mm-ss-## where ## is a sequence num.
    :param dirName - string with the fully qualified path to the files
    :param newNameList - list of processedName objects, ready to be applied to HDD
    """

    errorCount = 0

    #for shortName in dirList:
    for n in newNameList:
        fname = dirName + '/' + n.origName

        if os.path.isfile(fname):
            if n.type in INCLUDED_STILL_TYPES:
                #print ("File name is " + fname)
                try:
                    newName = dirName + '/' + n.newName
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

def setupStillsRename():
    '''
    get the folder name for processing
    '''
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
    # for n in newNames:
    #     print(n)
    renameStillsFolder(stillsPath,newNames)
    print ('Done. Execution took {:0.3f} seconds'.format((time.time() - start_time)))

    # TODO Double check what happens to sequence numbers on renaming renamed files. Seems to be dependent on natural order?
    # maybe sort by EXIF date if seq is the same for the whole folder (since it defaults to year in this case)

def setupVideoRename():
    '''
    get the folder name for processing
    Ultimately, this will be called by a GUI button?
    '''
    videoPath = filedialog.askdirectory(
                title = "Directory in which to rename jpg & ARW & CR2 & Tif files ",
                initialdir = "C:/Users/grant/Documents/scratch/sonySDStructure/DCIM/10060708"
                )

    print(videoPath)
    # Exit on cancel!
    if videoPath == "" : return

    start_time=time.time()

    # for n in newNames:
    #     print(n)
    print("renameVid output:"+ str(renameVideoFolder(videoPath)))

    print ('Done. Execution took {:0.3f} seconds'.format((time.time() - start_time)))

def traverseMediaTree(mediaSource):
    '''
    create two lists of mediaItems (stills & video) of the media in mediaSource to

    Must deal with media at all levels, from root and down,
       traverse any sub-dirs found (ala Sony), or deal with mixed contents (ala Canon)
        Largely based on
        http://stackoverflow.com/users/1126776/dmytro
        http://stackoverflow.com/questions/22078621/python-how-to-copy-files-fast
        removed the symlink stuff - will only work on 'real'  dirs
    '''

    # any FILES at root level
    names = os.listdir(mediaSource)
    errors = []
    for name in names:
        srcname = mediaSource + '/' +name
        #try:
        if os.path.isdir(srcname):
            traverseMediaTree(srcname)
        else:
            newMI = mediaItem(srcname[:srcname.rfind('/')+1],srcname[srcname.rfind('/')+1:] )
            if newMI.StillVideo == 'S':
                stillsList.append(newMI)
            if newMI.StillVideo == 'V':
                videoList.append(newMI)
            # print(srcname)
            
        #except:

    if errors:
        raise CTError(errors)


def setupDirCopy():
    '''
    Setup the dirs - a shim to interface with the GUI when it comes
    Copy and rename all the media from a user-selected dir to a stills and a video dir, each day getting it's own folder
    Must traverse any sub-dirs found (ala Sony), or deal with mixed contents (ala Canon)

    Some of this could be in objectified variously. NExt phase ...
    '''

    # Get the source
    mediaSourcePath = filedialog.askdirectory(
            title = "SOURCE of media (eg SD Card root) ",
            initialdir = "C:/Users/grant/Documents/scratch/sonySDStructure/"
            )

    # Root of the destinations. Currently hardcoded. Ultimately will be in the GUI option setter
    # add in a subdir for each day in the dir-walk
    # stillRootDestination = "C:/Users/grant/Pictures/2016/"
    # videoRootDestination = "C:/Users/grant/Videos/2016/"
    # test values:
    stillRootDestination = "C:/Users/grant/Documents/scratch/P2016/"
    videoRootDestination = "C:/Users/grant/Documents/scratch/V2016/"

    if not os.path.isdir(stillRootDestination):
        os.mkdir(stillRootDestination)

    if not os.path.isdir(videoRootDestination):
        os.mkdir(videoRootDestination)

    copyCount = 0

    start_time=time.time()
    # DONE: use an extension of processedName, Add attribs: still/video; abs src dir; abs dest dir; size; Date
    # Recursively traverse mediaSource, and get out all the INCLUDED* files into twolists - stillsSrc, videoSrc. Include srcDir
    # these could be parameters, but it will get confusing.
    global stillsList
    stillsList= []

    global videoList
    videoList = []

    traverseMediaTree(mediaSourcePath)
    #
    # STILLS
    # now get all the metadata
    for s in stillsList:
        s.updateMediaTags()
        # print(s)

    # create a list of stillsDests and videoDests, and mark which files must go where
    stillsList.sort(key = lambda v:v.dateTime)
    stillsDirs = []
    for s in stillsList:
        d = s.getDate() # s.dateTime.strftime("%Y_%m_%d")
        if d not in stillsDirs:
            stillsDirs.append(d)

    # stills - sequences don't last longer than one second, so the old sequence naming code is fine

    #find sequences in same file types
    prevDateTime = ""  # dateTime is always set, thus this will work for 1st iteration.
    prevfileType = ""
    seqTrack = 0
    #
    #sort by type to find same-second sequences
    stillsList.sort(key = attrgetter('fileType', 'origSeq'))

    # uses indexing to deal with the 'previous' element in a sequence
    for i in range(len(stillsList)):
        if stillsList[i].dateTime == prevDateTime and stillsList[i].fileType == prevfileType:
            if seqTrack == 0: # on the first one of a seq, go back and fix the previous
                stillsList[i-1].seq = seqTrack
                seqTrack += 1
            stillsList[i].seq = seqTrack
            seqTrack += 1
        else:
            seqTrack = 0
    
        prevDateTime = stillsList[i].dateTime
        prevfileType = stillsList[i].fileType
    #
    #sequencing sorted, now build the file names
    for sd in stillsList:
        if sd.seq != -1:
            sd.nameSuffix = "-%02d" % sd.seq
        sd.newName = sd.namePrefix + sd.newName + sd.nameSuffix + '.' + sd.fileType
        sd.newPath = stillRootDestination + sd.getDate() + '/'

    # create all the stiils dirs
    # List of failed folders
    stillFolderErr = []
    for s in stillsDirs:
        try:
            # print(stillRootDestination+s)
            if not os.path.isdir(stillRootDestination+s):
                os.mkdir(stillRootDestination+s)
        except:
            print(traceback.format_exc())
            # track folders errors
            stillFolderErr.append(stillRootDestination+s)
            #Todo: Exit(103) with message

    # now copy the stills files
    stillsFileErr = [ ]
    for sd in stillsList:
        try:
            # note shutil.copy2 preserves more OS level metadata
            # currently will overwrite if already exists
            # TODO: add a 'overwrite' all check
            shutil.copy2(sd.origPath + sd.origName , sd.newPath + sd.newName)
            copyCount += 1
            print('.',end='')
        except:
            print(traceback.format_exc())
            stillsFileErr.append(sd.origPath + sd.origName)
            # Todo: Exit(104) with message

    # VIDEO

    # Do sequence renaming
    for v in videoList:
        # update meta data
        v.updateMediaTags()

    videoList.sort(key = lambda v:v.dateTime)
    videoDirs = []
    for v in videoList:
        d = v.getDate() #v.dateTime.strftime("%Y_%m_%d")
        if d not in videoDirs:
            videoDirs.append(d)

    # create the new names for all the files.
    # This requires the complete meta in place, so can't be done in the previous loop!
    # for this version, simply let seq run across all videos in the dir

    seqCount = 0
    for vd in videoList:
        # TODO: prefix may get generalised in the GUI for camera ID, etc
        vd.namePrefix = "V%d_" % seqCount
        seqCount += 1
        vd.newName = vd.namePrefix + vd.newName + vd.nameSuffix + '.' + vd.fileType
        vd.newPath = videoRootDestination + vd.getDate() + '/'

        # print('nv:' + str(vd))

    # create all the video dirs
    # List of failed folders
    vidFolderErr = []
    #Todo: DAMP over DRY - refactor v to vidItem
    for v in videoDirs:
        try:
            # print(videoRootDestination+v)
            if not os.path.isdir(videoRootDestination+v):
                os.mkdir(videoRootDestination+v)
        except:
            print(traceback.format_exc())
            # track folders errors
            vidFolderErr.append(videoRootDestination+v)

    # now copy videos
    vidFileErr = []
    for vd in videoList:
        try:
            # note shutil.copy2 preserves more OS level metadata
            #currently will overwrite if already exists
            # TODO: add a 'overwrite' all check
            shutil.copy2(vd.origPath + vd.origName , vd.newPath + vd.newName)
            copyCount += 1
            print('.',end='')
        except:
            print(traceback.format_exc())
            vidFileErr.append(vd.origPath + vd.origName)


    print ('There were '+ str(len(vidFileErr)) + ' file and ' + str(len(vidFolderErr)) + ' folder errors' )
    print ('Done. copied ' + str(copyCount) + ' files in ' + str((time.time() - start_time)) + 'seconds' )
    return

def main():

    #launch and close the root window
    root = tk.Tk()
    root.withdraw()

    # for testing with just one file
    # srcname =filedialog.askopensrcname(
    #         title = "Media file to query:",
    #         initialdir = "C:/Users/grant/Documents/scratch/sonySDStructure"
    #         )
    #
    # print(srcname)
    # newItem = mediaItem(srcname[:srcname.rfind('/')+1],srcname[srcname.rfind('/')+1:] )
    # print(newItem)
    # newItem.updateMediaTags()
    # print(newItem)
    # mediaList = []
    # mediaList.append()
    # setupStillsRename()

    # setupVideoRename()


    #
    setupDirCopy()

    # if srcname != "" :
    #     print('\n'+srcname + ' becomes ' + getEXIFTime(srcname))


if __name__ == '__main__':
    main()