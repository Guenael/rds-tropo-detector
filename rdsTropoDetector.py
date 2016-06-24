#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#  
#  FreeBSD License
#  Copyright (c) 2016, Guenael
#  All rights reserved.
#  
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#  
#  1. Redistributions of source code must retain the above copyright notice, this
#     list of conditions and the following disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#  
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
#  ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#  

import math
import time
import datetime
import osmosdr
import rds
import pmt

from gnuradio import gr
from gnuradio import blocks
from gnuradio import analog
from gnuradio import digital;import cmath
from gnuradio import eng_notation
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio.eng_option import eng_option
from optparse import OptionParser
from gnuradio.gr.pubsub import pubsub
from gnuradio.eng_option import eng_option


class rds_pi(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name = "rds_pi",
            in_sig = None,
            out_sig = None,
        )
        self.message_port_register_in(pmt.intern('in'))
        self.set_msg_handler(pmt.intern('in'), self.handle_msg)
        self.stationID = None

    def handle_msg(self, msg):
        if(pmt.is_tuple(msg)):
            t = pmt.to_long(pmt.tuple_ref(msg, 0))
            m = pmt.symbol_to_string(pmt.tuple_ref(msg, 1))

            if (t==0):     #program information
                msg = unicode(m, errors='replace')
                self.stationID = msg
    
    def get_pi(self):
        return self.stationID

    def reset_pi(self):
        self.stationID = None


class rds_rx(gr.top_block, pubsub):

    def __init__(self, options, args):
        gr.top_block.__init__(self, "RDS Tropo Detector")
        pubsub.__init__(self)

        # Retrieve the selected options
        self.options = options
        self._verbose = options.verbose

        # Variables
        self.freq = 99.5e6
        self.samp_rate = 1000000  # TODO FIX : sampling rate
        self.bb_decim = 4
        self.freq_offset = baseband_rate = self.samp_rate/self.bb_decim
        self.audio_decim = 5
        self.xlate_bandwidth = 100000
        self.gain = 20
        self.freq_tune = self.freq - self.freq_offset

        # Initialize the device using OsmoSDR library
        self.src = osmosdr.source(options.args)
        try:
            self.src.get_sample_rates().start()
        except RuntimeError:
            print "Source has no sample rates (wrong device arguments?)."
            sys.exit(1)

        # Set the antenna
        if(options.antenna):
            self.src.set_antenna(options.antenna)

        # Apply the selected settings
        self.src.set_sample_rate(options.samp_rate)
        #self.src.set_sample_rate(self.samp_rate)
        self.src.set_center_freq(self.freq_tune, 0)
        self.src.set_freq_corr(0, 0)
        self.src.set_dc_offset_mode(0, 0)
        self.src.set_iq_balance_mode(0, 0)
        self.src.set_gain_mode(False, 0)
        self.src.set_gain(self.gain, 0)
        self.src.set_if_gain(20, 0)
        self.src.set_bb_gain(20, 0)
        self.src.set_antenna("", 0)
        self.src.set_bandwidth(0, 0)
          
        # Blocks
        self.fir_in = filter.freq_xlating_fir_filter_ccc(1, 
            (firdes.low_pass(1, self.samp_rate, self.xlate_bandwidth, 100000)), self.freq_offset, self.samp_rate)
        self.fm_demod = analog.wfm_rcv(
            quad_rate=self.samp_rate,
            audio_decimation=self.bb_decim,
        )
        self.fir_bb = filter.freq_xlating_fir_filter_fcf(
            self.audio_decim, (firdes.low_pass(2500.0,baseband_rate,2.4e3,2e3,firdes.WIN_HAMMING)), 
            57e3, baseband_rate)
        self.rrc = filter.fir_filter_ccf(1, firdes.root_raised_cosine(
            1, self.samp_rate/self.bb_decim/self.audio_decim, 2375, 1, 100))
        self.mpsk_demod = digital.mpsk_receiver_cc(2, 0, 1*cmath.pi/100.0, 
            -0.06, 0.06, 0.5, 0.05, self.samp_rate/self.bb_decim/self.audio_decim/ 2375.0, 0.001, 0.005)
        self.complex_to_real = blocks.complex_to_real(1)
        self.slicer = digital.binary_slicer_fb()
        self.skip = blocks.keep_one_in_n(1, 2)
        self.diff = digital.diff_decoder_bb(2)

        self.rds_decoder = rds.decoder(False, False)
        self.rds_parser = rds.parser(False, False, 1)
        self.rds_pi_extract = rds_pi()

        # Connections
        self.connect((self.src, 0), (self.fir_in, 0))    
        self.connect((self.fir_in, 0), (self.fm_demod, 0))    
        self.connect((self.fm_demod, 0), (self.fir_bb, 0))    
        self.connect((self.fir_bb, 0), (self.rrc, 0))    
        self.connect((self.rrc, 0), (self.mpsk_demod, 0))    
        self.connect((self.mpsk_demod, 0), (self.complex_to_real, 0))    
        self.connect((self.complex_to_real, 0), (self.slicer, 0))    
        self.connect((self.slicer, 0), (self.skip, 0))    
        self.connect((self.skip, 0), (self.diff, 0))    
        self.connect((self.diff, 0), (self.rds_decoder, 0))    
        self.msg_connect((self.rds_decoder, 'out'), (self.rds_parser, 'in'))    
        self.msg_connect((self.rds_parser, 'out'), (self.rds_pi_extract, 'in'))  

    def set_frequency(self, freq=None):
        self.freq = freq
        self.freq_tune = self.freq - self.freq_offset
        self.src.set_center_freq(self.freq_tune, 0)


def get_options():
    usage="%prog: [options]"
    parser = OptionParser(option_class=eng_option, usage=usage)

    parser.add_option("-a", "--args", type="string", default="",
                      help="Device args, [default=%default]")
    parser.add_option("-A", "--antenna", type="string", default=None,
                      help="Select RX antenna where appropriate")
    parser.add_option("-s", "--samp-rate", type="eng_float", default=1e6,
                      help="Set sample rate (bandwidth), minimum by default")
    parser.add_option("", "--start-freq", type="eng_float", default=88.1,
                      help="Set start frequency [default=%default]")
    parser.add_option("", "--stop-freq", type="eng_float", default=107.9,
                      help="Set start frequency [default=%default]")
    parser.add_option("", "--step", type="eng_float", default=0.2,
                      help="Set step frequency [default=%default]")
    parser.add_option("-c", "--freq-corr", type="eng_float", default=None,
                      help="Set frequency correction (ppm)")
    parser.add_option("-g", "--gain", type="eng_float", default=19,
                      help="Set gain in dB (default is midpoint)")
    parser.add_option("-v", "--verbose", action="store_true", default=False,
                      help="Use verbose console output [default=%default]")

    (options, args) = parser.parse_args()
    if len(args) != 0:
        parser.print_help()
        raise SystemExit, 1

    return (options, args)


if __name__ == '__main__':
    (options, args) = get_options()

    print "Settings:"
    print "---Start frequency (MHz) :", options.start_freq
    print "---Stopfrequency   (MHz) :", options.stop_freq
    print "---Step size       (MHz) :", options.step
    print "---RX gain         (dB)  :", options.gain
    print "---Sampling rate   (sps) :", options.samp_rate

    tb = rds_rx(options, args)
    
    #piCount = 0
    while True:
        for n in xrange(0, int( (options.stop_freq-options.start_freq)/options.step ) ):  # number of sweep
            freq = options.start_freq + (n * options.step)
            
            tb.set_frequency( freq * 1e6)
            tb.rds_pi_extract.reset_pi()
            
            tb.start()
            time.sleep(2)
            tb.stop()
            tb.wait()
            
            pi = tb.rds_pi_extract.get_pi()
            date = datetime.datetime.now().strftime("%Y-%m-%d,%H:%M")
            
            if pi:
                print str(date)+","+str(freq)+","+str(pi)
                #piCount = piCount + 1

        #print "Total:", piCount
        #piCount = 0