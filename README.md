# PhotoTransfer
MediaTransfer App in Python.
Its purpose is to read through a camera media card, and copy the stills and movies in into  given directories, grouping files into directories for each day (folders are named yyyy_mm_dd), and renaming them to yyyy-mm-dd hh-mm-ss format. It takes into account multiple stills in the same second, and calculates the start time of movies, to make sync-ing with audio easier. 

It uses the built-in metadata rather than OS level metadata whereever possible, via exifread and MediaInfo.
There are many other metadata tags that could be added/ used, but date and time are the core for managing media in the long term.

Requires 
  https://pypi.python.org/pypi/ExifRead 
and 
  https://mediaarea.net/en/MediaInfo/Download
  
Still need to check versions, but this was developed on Windows 7 with the latest 64 bit versions of these libaries.

exifread and MediaInfoDLL3 must be in the same path as Rename&TransferMedia.py

Target dirs are still hardcoded in setupDirCopy(), but you are prompted for the source dir. Rename them to where you want the copy to go.

Rename only code can be uncommented in main()

Very basic version

Todo:
====
1. De-hardcode the target media dirs
2. De-hardcode swapping between rename a dir and copy everything from a card
3. Add a GUI. This is sketched out using PAGES. This will most probably be the method to solve 1 & 2!
4. Add GUI fields for date format strings and the prefix/ suffic tags
5. Potentially clean up the code - the rename code was the first iteration, and served as the basis for the copy, but they are different, and would ideally by consolidated. That said, I set out to write a copyAndRename utility, and would rather be spending my time now editing video, not writing code! The two threads each have merits, and may be useful as gists.

It is possible to use this to do meta-data based batch transcoding using some of the fine utilities out there like ffmpeg etc: RAW to TIF, non-25FPS video to 25FPS, to create proxies, etc. 

Thanks to the exifread and MediaInfo teams for rock-solid, fast and well documented libraries, and to StackOverflow for many little code fragment hints.

Licenced as a LGPL, but still need to confirm the licensing of the two libraries
