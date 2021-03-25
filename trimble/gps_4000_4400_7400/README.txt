
firmware files:
4000 receiver:
719B.X - official 7.19B firmware
719C.X - modified 7.19B firmware that fixes week rollover (not tested)
732.X - official 7.32 firmware
732B.X - modified 7.32 firmware that fixes week rollover

4400/7400 receiver:
C238.X - official C238.X file
C238B.X - modicied with week rollover fix




To load this firmware you need some older computer with dos support or run it in DOSBOX or DOSEMU. Ymmv.

You need to get loader from official firmware package. Download it, extract, copy FW you want to same directory and execute:

Command to load the firmware:
loader.exe -B38400 -R -Dx 732B.X
or slower variant
loader.exe -B9600 -R -Dx 732B.X

where -Dx stands for COMx, change x for the serial port your 4000 is connected to.


Responsibility is always yours!

