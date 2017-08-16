# Dav2Mp4
Batch convert security camera DAV videos into standard MP4s

Many security cameras export files in a proprietary DAV (Dahau) format. The various manufacturers viewing software are all awful to be point of being unusable. This program converts an exported folder of hundreds or thousands of small DAV video files to MP4, merges the contiguous ones into single longer MP4 files and preserves the original date-time information as subtitles that display as you view the videos.

Installation instructions:
Download Dav2Mp4.zip and unzip it. Run Dav2Mp4.exe.
Dav2Mp4.zip is a package created with pyinstaller to allow running the program without setting up a Python environment.


Dav2Mp4 is written in Python3. The user interface uses tkinter. The video files are currently converted with ffmpeg, but in a future update I'd like to directly use Dahua's SDK to convert the proprietary format directly. I have packaged the program into a binary with pyinstaller so the user doesn't have to install a python environment.

Note that it appears ffmpeg doesn't read the frame rates exactly and the converted video may play 5%-20% faster or slower than the original. I 'catch up' and correct the time stamp every time I get a timestamp in the file names. If this is a problem there is a program available for download at BahamaSecurity that uses the Dahua SDK directly to batch convert DAV files to AVI files which appear to be closer but still not perfect either. You can use the BahamaSecurity program to convert to AVI then use this program to merge and timestamp the resulting files. Even the manufacturers viewing software plays a different duration than the times marked on the files names, so perfection may not be attainable with these security cameras.


