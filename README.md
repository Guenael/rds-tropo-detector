# rdsTropoDetector -- A simple propagation detector using RDS system from FM broadcasting

*Work in progress -- Tests & PoC*

Special atmospheric events allow uncommon long distance communications on some frequency bands, and these events are specially appreciated by radio-amateurs. The main goal of this tiny application is to detect these phenomena by detecting the presence of new FM broadcasting stations. The application scan the whole FM segment (88-108 MHz) and reports ID used by each station found using RDS system. Statistics could be made and shared on Internet to report some unusual condition.

<h2>Dependencies & framework used</h2>

This code is based on gr-rds, written by Bastian Bloessl.
https://github.com/bastibl/gr-rds

<h2>Keywords:</h2>
radio, propagation, detection, vhf, fm, rds

<h3>Basically, this application :</h3>
- Use osmosdr to open your preferred SDR (http://sdr.osmocom.org/trac/wiki/GrOsmoSDR)
- Set a frequency between 88 and 108 MHz (with a step of 200kHz)
- Try to decode the ID of possible FM station (during 2 sec)
- Print the result if an ID is found
- Loop...

<h3>Howto:</h3>
1. Install gnuradio & gr-rds
2. Plug your device & start this python application
3. Do you stat yourself :) (for now...)

<h3>Notes:</h3>
- Do not push the gain too high, to avoid multiple report (aliasing, IMD...)
- Use a good antenna, and a passband filter

<h3>TODO:</h3>
- update fixed sampling rate (1Msps)
- online reporting
- stats
- avoid multiple report for the same identifier
