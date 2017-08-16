# Dav2Mp4
# V1.4 - Peter@PeterTheobald.com 2017
# GPLv3 license
#
# Convert folder full of surveillance system DAV videos to standard MP4 videos
# Works with NVR DAV files with filename convention:
#    NPV-CH<camera-channel>-<track:MAIN or ALT>-<yyyymmddhhMMss>-<yyyymmddhhMMss>{_1}.DAV
# This includes the ICrealtime, Dahua, and other camera systems
# Preserve embedded DAV DateTime info by using the filenames and DateTime subtitles
# Also merge hundreds of small clips into larger duration MP4 video files
#
# If you are having trouble converting your DAV files using this Dav2Mp4 you may need
# to choose the nuclear option: go purchase 'Amped DVRconv' which specializes in
# converting security cam video
# Note: The original EOM Dahua software, which is white-labelled by every other
# manufacturer is terrible. When playing video files the times do not match the
# filename's encoded times. The durations do not match. The timeline cursor starts
# in one area then jumps to another. Export fails more often than it succeeds with
# unhelpful errors such as 'file too small export failed'
# (tested with Dahua Smart Player 3.41.0.R.161031 and several other versions)
#
# BahamaSecurity DHAVI Batch Converter 3.34 works pretty well to convert DAV to AVI
#   It is both faster and converts closer (but not perfect) frame rates/durations
#   than ffmpeg. Use Dav2Mp4 to merge the hundreds of small AVIs and subtitle them.

# Python 3, tk, ttk, ffmpeg
# draw UI:
#    title
#    left: DAV folder, DAV file list, CONVERT button, right: MP4 folder, MP4 file list
#    progress bar
#    console/log
# on convert:
#    convert all DAV files to MP4 files (must convert before durations are available)
#    apply DateTime subtitles to MP4 files
#    merge adjacent time MP4 files

# Version history/roadmap:
# V0.1: basic UI to select DAV folder, MP4 folder
# V0.2: subprocess ffmpeg to convert DAV to MP4
# V0.3: build DateTime subtitle files
# V0.4: merge time-adjacent files from same camera/channel
# V0.5: dont make merged videos larger than maximum 2GB
# V0.6: handle files w same name same time period _1 suffix but different actual contents
#         use the larger one but note the exception
#V1.0
# V1.0: package into pyinstaller executable, make sure ffmpeg and ffprobe are in path or cwd
# V1.1: create 2 log files dav2mp4-log.txt and dav2mp4-debug.txt (w ffmpeg output)
# V1.2: checkboxes/settings for partial processing: Dav2Mp4, Merge Mp4s, timestamp subtitles
# V1.3: ability to work with BahamaSecurity batch converter.
#       Use Bahama to convert to avi, then merge and subtitle here
# V1.4: redo GUI to better show steps: dav->mp4, merge, subtitle
# TODO: burn/stamp DateTime subtitles onto mp4 videos
# TODO: handle mp4 duration differences from recorded filename duration - analyze for best results
# TODO: move ffmpeg into multithreading process and add CANCEL button so UI doesn't freeze
# TODO: about button w description, my contact info, GPL license
# TODO: Color filename backgrounds green as they are finished
#V2.0: Converting in background!
# TODO: add timestamps to log files
# TODO: minimize transcoding passes,
#       reduce 3 passes (dav->mp4,merge mp4s,burn subtitles) to as few passes as possible
# TODO: optimize video codecs/frame rates/options for transcoding
# TODO: add option to merge all files, even non-contiguous ones
# TODO: remember last used folders and default to them
# TODO: switch from ffmpeg to Dahua's SDK to transcode their proprietary frame rate weirdness
#       and get durations that are closer but still not correct.
#       SDK is C++, write command line davsdk2avi.exe infile-full-path outfile-full-path
# TODO: add support for filename convention: <cam>-<startdatetime>.DAV
# TODO: add fancy windows installer
# TODO: add instructions for build environment (pyinstaller, ffmpeg etc)
# TODO: support other subtitle formats other than SRT (ASS, SSA) and have options to set screen location
# TODO: add better error handling to catch any errors and display/log them nicely

# technique notes:
# Subtitles: filename.srt line1: seqid, line2: starttime --> endtime, line3-n: text, blank-line
#   time= hh:mm:ss,ms eg 00:20:41,150
#   soft subtitles put in .srt file, show subtitles in viewer. hard: ffmpeg -vf subtitles=file.srt
# video merging: (same codec) concat "demuxer" will merge without reencoding
#      ffmpeg -f concat -safe 0 -i filelist.txt -c copy output.mp4 (stream copy no reencoding) (filelist.txt=file file1.mp4\nfile file2.mp4\nfile file3.mp4)
# querying duration:
#   ffprobe -v quiet -print_format compact=print_section=0:nokey=1:escape=csv -show_entries format=duration "$input_file" (in seconds) or -sexagesimal (in 00:20:00,200 format)
#   pipe=sp.Popen(['ffprobe'], stdout=sp.PIPE, stderr=sp.STDOUT)
#   duration, err = pipe.communicate()

import sys, os, glob
import subprocess
import datetime
import collections
import shutil

from tkinter import * # no prefixes
import tkinter.scrolledtext as tkst
from tkinter import ttk # use ttk.prefix
from tkinter import filedialog
from tkinter import messagebox

# init_commands:
# get path to executables:
if getattr(sys, 'frozen', False):
  # we are running in a pyinstaller bundle
  bundle_dir = sys._MEIPASS
else:
  # we are running in a normal Python environment
  bundle_dir = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join( bundle_dir, 'ffmpeg.exe')
FFPROBE = os.path.join( bundle_dir, 'ffprobe.exe')

### Logging functions ##########################
#   note Python-style prefers module level fns over Java-style never-instantiated static Class methods
_LOGFILE='dav2mp4-log.txt'
_DEBUGFILE='dav2mp4-debug.txt'
_logfile_f=None
_debugfile_f=None

def path( folder, file):
  # use normpath to fix problems such as tk browser widget
  # always returning Linux paths even on Windows systems
  return( os.path.normpath(os.path.join( folder, file)))

def log( text, folder=None):
  # sends text to logfile, can send strings or bytes
  global _logfile_f, _debugfile_f
  if (folder):
    _logfile_f=open( path( folder, _LOGFILE),'wb')
    _debugfile_f=open( path( folder, _DEBUGFILE),'wb')
  if (text):
    try:
      text=text.encode() # convert str to utf8
    except AttributeError:
      pass
    _logfile_f.write( text + b'\n')
    _logfile_f.flush()
    ui.log(text.decode())
    debug(b'---- '+text)
    
def debug( text):
  # sends text to logfile, can send strings or bytes
  if (text):
    try:
      text=text.encode() # convert str to utf8
    except AttributeError:
      pass
    _debugfile_f.write( text + b'\n')
    _debugfile_f.flush()
################################################

def runConversions( davFolder, mp4Folder, mergedFolder):
  log( "starting conversion", mp4Folder)
  progress=0
  if (ui.runDav2Mp4.get()):
    # convert all dav to mp4
    log('---- converting DAV to MP4')
    ui.updateProgress(0.0)
    ui.clearFileList()
    davFiles=sorted(filter(lambda x: x.endswith(('.dav','.DAV')), os.listdir(davFolder)))
    if (ui.runMergeMp4.get()):
      maxProgress=len(davFiles*2) # two passes
    else:
      maxProgress=len(davFiles) # one pass
    for file in davFiles:
      log('converting '+file+" to mp4...")
      mp4file = re.sub( r'\.[dD][aA][vV]$', '.mp4', file)
      convertDav2Mp4( path(davFolder, file), path(mp4Folder, mp4file))
      progress+=1
      ui.addToFileList( mp4file)
      ui.updateProgress( 100.0*progress/maxProgress)
  
  if (ui.runMergeMp4.get()):
    # merge adjacent mp4s, build datetime subtitles
    log('---- Merging consecutive videos')
    mp4Files=sorted(filter(lambda x: x.endswith(('.mp4','.MP4','.avi','.AVI')), os.listdir(mp4Folder)))
    maxProgress=progress+len(mp4Files)
    prevFile=''
    mergeList=[] # keep list of contiguous files and merge contiguous groups
    mergedSize=0 # track merged file size to avoid going over 2GB
    debug('DB empty mergelist')
    for file in mp4Files:
      debug('DB mergelist='+str(mergeList))
      fInfo=getVideoFileInfo( file, mp4Folder)
      if (prevFile == '' or areContiguous(file, prevFile)):
        debug('DB nearlyadj '+file)
        if (mergedSize+fInfo.fileSize < 2000000000):
          mergeList.append(file) # add to list of contiguous files
          mergedSize+=fInfo.fileSize
          log('merging '+file+'...')
        else:
          debug('DB too large, merge list and start new')
          # merged file would be too large, merge whats on the list and start a new one
          performMerge( mergeList, mp4Folder, mergedFolder)
          mergeList=[file]
          mergedSize=fInfo.fileSize
          log('merging '+file+'...')
      elif (sameDatetime(file, prevFile)):
        # an anomaly has been observed: two files w the same recorded time range
        # one with _1 appended, but w different file sizes and actual durations
        # usually the smaller duration is less then the recorded time range
        # and the larger duration is greater than the recorded time range
        # neither file duration matches their file name encoded time range
        # Keep the longer file, but warn about the discrepancy in the console
        # and in the datetime subtitles
        debug('DB sametime'+file)
        prevfInfo=getVideoFileInfo( prevFile, mp4Folder)
        if (fInfo.fileSize>prevfInfo.fileSize):
          # replace the previous file with this longer version
          mergeList[-1]=file # keep the longer file
          mergedSize=mergedSize-prevfInfo.fileSize+fInfo.fileSize
          log('merging '+file+' instead of prev file...')
          file=prevFile
          # Note possible error: this larger file could cause a merged file > 2GB
          # TODO: handle that
        else:
          log('skipping '+file)
      else:
        # non-contiguous file
        debug('DB not contig '+file)
        performMerge( mergeList, mp4Folder, mergedFolder) # merge what we have
        mergeList=[file] # start a new list with current file
        mergedSize=fInfo.fileSize
        log('merging '+file+'...')
      prevFile=file
      progress+=1
      ui.updateProgress(100.0*progress/maxProgress)
    # finish last file(s):
    performMerge( mergeList, mp4Folder, mergedFolder)
    log('finished')
    ui.updateProgress(0.0)
    ui.clearFileList()
    for mp4file in sorted(filter(lambda x: x.endswith('.mp4'), os.listdir(mergedFolder))):
      ui.addToFileList( mp4file)
  
def convertDav2Mp4( davPath, mp4Path):
  command = [FFMPEG, '-y', '-i', davPath, mp4Path]
  debug(str(command))
  pipe= subprocess.Popen( command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err =pipe.communicate()
  debug(out)
  debug(err)

def areContiguous( filename, prevFilename):
  # return true if the startDatetime encoded in filename
  # is the same as the  endDateTime endoded in prevFilename
  # -- I've observed video files w duration of just 1 second
  #    so check for 2 second margin of error unless the file
  #    itself is less than 3 seconds then they have to be exact
  f1Info=getVideoFileInfo( filename)
  f2Info=getVideoFileInfo( prevFilename)
  f1StartDatetime=datetime.datetime.strptime( f1Info.namedStartTime, '%Y%m%d%H%M%S')
  f2EndDatetime=datetime.datetime.strptime( f2Info.namedEndTime, '%Y%m%d%H%M%S')
  timeDifference=abs((f2EndDatetime-f1StartDatetime).total_seconds()) # timedelta object
  debug('DB Nearly adjacent: file1 '+prevFilename+' time '+f2Info.namedEndTime+' vs. file2 '+filename+' time '+f1Info.namedStartTime+' = '+str(timeDifference)+'\n')
  if (f1Info.namedDuration<3):
    # must be an exact match
    return (timeDifference==0)
  else:
    return (timeDifference<=2)
  
def sameDatetime( filename1, filename2):
  f1Info=getVideoFileInfo( filename1)
  f2Info=getVideoFileInfo( filename2)
  return( f1Info.namedStartTime==f2Info.namedStartTime and f1Info.namedEndTime==f2Info.namedEndTime)
  
def performMerge( mergeList, mp4Folder, mergedFolder):
  # calc merged filename with the first file's startDatetime, the last file's endDatetime
  # merge the videos
  # create a subtitle file w one second long segments for each merged file
  #    *beware: some files are recorded wrong with different recorded durations and observed durations
  #     TODO: handle these by checking ffprobe observed duration and created dual subtitles
  # move the handled files into subdirectory 'merged/'
  # ffmpeg -f concat -safe 0 -i filelist.txt -c copy output.mp4 (stream copy no reencoding) (filelist.txt=file file1.mp4\nfile file2.mp4\nfile file3.mp4)

  firstInfo=getVideoFileInfo( mergeList[0]) # doesnt need folder, all info is in filename
  lastInfo=getVideoFileInfo( mergeList[-1])
  
  debug('performMerge: '+str(mergeList))
  # create merged video:
  if (len(mergeList)>1):
    mergedMp4File = firstInfo.namedPrefix + firstInfo.namedStartTime + '_' + lastInfo.namedEndTime + '.mp4'
    mergeListTxtFile = path( mp4Folder, 'Dav2Mp4-mergelist.txt')
    debug('DB: mergeListTxtFile=',mergeListTxtFile,'\n')
    with open( mergeListTxtFile,'w') as f:
      for file in mergeList:
        f.write('file \''+path( mp4Folder, file)+'\'\n')
        debug('DB:MergeListTxtFile   ',path( mp4Folder, file),'\n')
    # DB
    #mergeListTxtFileDB = path( folder, 'Dav2Mp4-mergelist-debug.txt')
    #shutil.copy(mergeListTxtFile, mergeListTxtFileDB)
    command=[FFMPEG, '-f', 'concat', '-safe' , '0', '-i', mergeListTxtFile,
             '-y', '-c', 'copy', path(mergedFolder, mergedMp4File)]
    debug(str(command))
    pipe= subprocess.Popen( command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err =pipe.communicate()
    debug(out)
    debug(err)
    log('merged to '+mergedMp4File)
  
  # create subtitle file:
  # srt file: <seqid> / hh:mm:ss,ms --> hh:mm:ss,ms / text / blank
  #   hh:mm:ss is relative to start. text is absolute Datetime in human readable fmt
  #
  # Track two simultaneous times:
  #   1) The cumulative SRT start and stop times (in seconds) for each subtitle
  #   2) The display Datetime from the surveillance camera

  subtitleFile = firstInfo.namedPrefix + firstInfo.namedStartTime + '_' + lastInfo.namedEndTime + '.srt'
  log('building timestamp subtitle file '+subtitleFile)
  srtID=1
  srtTime=0.0
  debug('DB mergelist=', mergeList, '\n')
  with open( path( mergedFolder, subtitleFile), 'w') as f2:
    for file in mergeList:
      videoFileInfo = getVideoFileInfo( file, mp4Folder)
      # displayStartTime = videoFileInfo.namedStartTimeObj (datetime.datetime)
      debug('DB file='+file+' videoDuration=',videoFileInfo.videoDuration,' namedDuration=',videoFileInfo.namedDuration,'\n')
      for fileTime in range(0, int(videoFileInfo.videoDuration+1.0)):
        if ((fileTime+0.999)<=videoFileInfo.videoDuration):
          # count in 1 second intervals
          srtStart=srtTime+fileTime
          srtEnd=srtTime+fileTime+0.999
        else:
          # except at the end of the file end at the exact finish
          srtStart=srtTime+fileTime
          srtEnd=srtTime+videoFileInfo.videoDuration
        srtStartHours, srtStartRem=(srtStart//3600, srtStart%3600)
        srtStartMins, srtStartSecs=(srtStartRem//60, srtStartRem%60)
        srtStartMillis=srtStart%1
        srtEndHours, srtEndRem=(srtEnd//3600, srtEnd%3600)
        srtEndMins, srtEndSecs=(srtEndRem//60, srtEndRem%60)
        srtEndMillis=srtEnd%1
        srtTimeDisplay='{:02d}:{:02d}:{:02d},{:03d} --> {:02d}:{:02d}:{:02d},{:03d}'.format(
          int(srtStartHours), int(srtStartMins), int(srtStartSecs), int(srtStartMillis*1000),
          int(srtEndHours), int(srtEndMins), int(srtEndSecs), int(srtEndMillis*1000))
        displayDateTimeObj = videoFileInfo.namedStartTimeObj + datetime.timedelta(seconds=fileTime)
        displayDateTimeStr = displayDateTimeObj.strftime('%Y-%m-%d %H:%M:%S')
        f2.write(str(srtID)+'\n'+srtTimeDisplay+'\n'+displayDateTimeStr+'\n\n')
        srtID+=1
      srtTime+=videoFileInfo.videoDuration+0.001 # Next file start time
  # TODO: option to burn subtitles: ffmpeg -cf subtitles.srt

  # note: if its just one file, no merge happened, just copy file
  if (len(mergeList)==1):
    shutil.copy2( path(mp4Folder, file), path(mergedFolder, file))

def getVideoFileInfo( file, folder=''):
  # get info from DAV coded filename
  # if optional path is included get 'expensive' info from file itself
  # filename = <CAM>_<StartyyyymmddhhMMss>_<EndyyyymmddhhMMss>{_1}.mp4
  # dateTime= <yyyymmddhhMMss>
  namedPrefix, namedStartTimeStr, namedEndTimeStr = re.match(r'(.*)(\d{14})[-_ ](\d{14})', file).groups() 
  namedStartTimeObj = datetime.datetime.strptime( namedStartTimeStr, '%Y%m%d%H%M%S')
  namedEndTimeObj = datetime.datetime.strptime( namedEndTimeStr, '%Y%m%d%H%M%S')
  namedDuration=(namedEndTimeObj-namedStartTimeObj).total_seconds()+1 # timedelta to float
  if (folder):
    command=[FFPROBE,'-v', 'quiet', '-print_format',
             'compact=print_section=0:nokey=1:escape=csv',
             '-show_entries', 'format=duration', path( folder, file)]
    #debug(str(command))
    pipe=subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    videoDuration, err = pipe.communicate()
    videoDuration=float(videoDuration.decode("utf-8").rstrip())
    #debug(err)
    fileSize=os.path.getsize( path(folder, file))
  else:
    videoDuration=None
    fileSize=None
  videoFileInfo = collections.namedtuple('videoFileInfo', ['namedPrefix', 'namedStartTime', 'namedEndTime', 'namedStartTimeObj', 'namedEndTimeObj', 'namedDuration', 'fileSize', 'videoDuration'])
  return videoFileInfo( namedPrefix, namedStartTimeStr, namedEndTimeStr, namedStartTimeObj, namedEndTimeObj, namedDuration, fileSize, videoDuration)
  
################################

class UI(Frame):
  def __init__(self, master=None):
    Frame.__init__(self, master)
    self.pack(fill=BOTH,expand=1)
    self.create_widgets()
    self.processingState=0
  
  def davBrowser(self):
    folder = filedialog.askdirectory(title="Choose folder with DAV video files", mustexist=1)
    if folder:
      self.davFolder.set(folder)
      self.fileList.configure(state='normal')
      for file in sorted(filter(lambda x: x.endswith(('.dav','.DAV')), os.listdir(folder))):
         self.fileList.insert( "end", file+"\n")
      self.fileList.configure(state='disabled')
  
  def updateProgress(self, progress):
    self.progressVar.set(progress)
    self.update()
    
  def mp4Browser(self):
    folder = filedialog.askdirectory(title="Choose folder for MP4/AVI video files", mustexist=0)
    if folder:
      self.mp4Folder.set(folder)
      self.fileList.configure(state='normal')
      for file in sorted(filter(lambda x: x.endswith(('.mp4','.MP4','.avi','.AVI')), os.listdir(folder))):
         self.fileList.insert( "end", file+"\n")
      self.fileList.configure(state='disabled')
      
  def mergedBrowser(self):
    folder = filedialog.askdirectory(title="Choose folder to save merged MP4 video files", mustexist=0)
    if folder:
      self.mergedFolder.set(folder)
      
  def clearFileList(self):
    self.fileList.configure(state='normal')
    self.fileList.delete("1.0",END)
    self.fileList.configure(state='disabled')
    
  def addToFileList(self, text):
    self.fileList.configure(state='normal')
    self.fileList.insert("end", text+"\n")
    self.fileList.configure(state='disabled')
    
  def convertHandler(self):
    if (self.runDav2Mp4.get() and not self.davFolder.get()):
      messagebox.showerror("Error", "Select folder with DAV video files to convert")
    elif (self.runDav2Mp4.get() and not self.mp4Folder.get()):
      messagebox.showerror("Error", "Select folder to save MP4 video files")
    elif (self.runMergeMp4.get() and not self.mp4Folder.get()):
      messagebox.showerror("Error", "Select folder with MP4 or AVI video files to merge")
    elif (self.runMergeMp4.get() and not self.mergedFolder.get()):
      messagebox.showerror("Error", "Select folder to save merged MP4 video files")
    else:
      if self.processingState==0: # I call update from inside the loop, catch thread-unsafe call
        self.processingState=1
        # ghost Convert button. Add 'spinner' widget/dialog w cancel button
        runConversions( self.davFolder.get(), self.mp4Folder.get(), self.mergedFolder.get())
        self.processingState=0

  def log(self, message):
    self.consoleLog.configure(state='normal')
    self.consoleLog.insert('end', message+'\n')
    self.consoleLog.configure(state='disabled')
    self.update()
    
  def create_widgets(self):
    # [header]
    # [DavLabel][DavFolder][DavBrowseButton][Mp4Label][Mp4Folder][Mp4BrowseButton]
    # [DavFileList] [convertButton] [Mp4FileList]
    # [progressBar]
    # [consoleLog]

    # main layout:
    self.header = ttk.Label(self, text="Convert surveillance cam DAV video to standard MP4 video")
    self.header.pack(padx=3, pady=3)
    
    # DAV folder selector:
    self.DavSelector = ttk.Frame(self)
    self.DavSelector.pack(fill=X)
    self.davFolderLabel = ttk.Label(self.DavSelector, text="DAV folder:")
    self.davFolderLabel.pack(side="left")
    self.davFolder=StringVar()
    # TODO: add onChange handler for entry widget
    self.davFolderEntry = ttk.Entry(self.DavSelector, width=0, textvariable=self.davFolder)
    self.davFolderEntry.pack(side="left",fill=X,expand=1)
    self.davBrowseButton = ttk.Button(self.DavSelector, text="Browse", command=self.davBrowser)
    self.davBrowseButton.pack(side="left", padx=3)
    
    # MP4 folder selector:
    self.mp4Selector = ttk.Frame(self)
    self.mp4Selector.pack(fill=X)
    self.mp4FolderLabel = ttk.Label(self.mp4Selector, text="MP4/AVI folder:")
    self.mp4FolderLabel.pack(side="left")
    self.mp4Folder=StringVar()
    # TODO: add onChange handler for entry widget
    self.mp4FolderEntry = ttk.Entry(self.mp4Selector, width=0, textvariable=self.mp4Folder)
    self.mp4FolderEntry.pack(side="left",fill=X,expand=1)
    self.mp4BrowseButton = ttk.Button(self.mp4Selector, text="Browse", command=self.mp4Browser)
    self.mp4BrowseButton.pack(side="left", padx=3)

    # Merged folder selector:
    self.mergedSelector = ttk.Frame(self)
    self.mergedSelector.pack(fill=X)
    self.mergedFolderLabel = ttk.Label(self.mergedSelector, text="Merged MP4 folder:")
    self.mergedFolderLabel.pack(side="left")
    self.mergedFolder=StringVar()
    # TODO: add onChange handler for entry widget
    self.mergedFolderEntry = ttk.Entry(self.mergedSelector, width=0, textvariable=self.mergedFolder)
    self.mergedFolderEntry.pack(side="left",fill=X,expand=1)
    self.mergedBrowseButton = ttk.Button(self.mergedSelector, text="Browse", command=self.mergedBrowser)
    self.mergedBrowseButton.pack(side="left", padx=3)
    
    # pass checkboxes:
    self.passSelections = ttk.Frame(self, borderwidth=2, relief=GROOVE)
    self.passSelections.pack(fill=X, pady=3)
    self.runDav2Mp4=IntVar()
    self.runDav2Mp4.set(1)
    self.checkRunDav2Mp4 = ttk.Checkbutton(self.passSelections, text="convert DAVs to MP4 w ffmpeg", variable=self.runDav2Mp4)
    self.checkRunDav2Mp4.pack(fill=X)
    #self.dummy = ttk.Checkbutton(self.passSelections, text="convert DAVs to AVI w BahamaSecurity", state=DISABLED)
    #self.dummy.pack(fill=X)
    #self.dummy = ttk.Checkbutton(self.passSelections, text="convert DAVs to AVI w DahuaSDK", state=DISABLED)
    #self.dummy.pack(fill=X)
    self.runMergeMp4=IntVar()
    self.runMergeMp4.set(1)
    self.checkRunMergeMp4 = ttk.Checkbutton(self.passSelections, text="Merge contiguous MP4s/AVIs and make timestamp subtitles", variable=self.runMergeMp4)
    self.checkRunMergeMp4.pack(fill=X)
    
    # GO button and Progress bar
    self.progressFrame = ttk.Frame(self)
    self.progressFrame.pack(fill=X)
    self.convertButton = ttk.Button(self.progressFrame, text="Convert=>", command=self.convertHandler)
    self.convertButton.pack(side="left", padx=3)
    self.progressVar=DoubleVar()
    self.progressBar = ttk.Progressbar(self.progressFrame,
      mode="determinate", orient="horizontal",
      maximum=100.0, value=0.0, variable=self.progressVar)
    self.progressBar.pack(fill=X, padx=3, pady=5)
    
    # Files list and console/log text:
    self.fileList = tkst.ScrolledText(self, width=10, height=3, state='disabled')
    self.fileList.pack(fill=BOTH,expand=1)
    self.consoleLog = tkst.ScrolledText(self, width=10, height=3, state='disabled')
    self.consoleLog.pack(fill=BOTH,expand=1)

################################
    
root = Tk()
ui = UI(master=root)
ui.master.title("Dav2Mp4")
ui.master.geometry("800x600")
ui.mainloop()

  
