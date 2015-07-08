#!/usr/bin/env python

from dsmrp1 import *

import sys

def main():
    if len(sys.argv) == 1:
        m = Meter('/dev/P1')
        tg = m.read_telegram()
        kWh = int((tg['kWh'] + tg['kWh-low']) *60*60*1000)
        dm3 = int(tg['gas'][1] *1000)
        print 'multigraph p1_kWh'
        print 'kWh.value %s' % kWh
        print
        print 'multigraph p1_dm3'
        print 'dm3.value %s' % dm3
        return 0
    if sys.argv[1] == 'config':
        print 'multigraph p1_kWh'
        print 'graph_title Electricity usage'
        print 'graph_vlabel Watt'
        print 'graph_category P1'
        print 'kWh.label Watt'
        print 'kWh.type DERIVE'
        print
        print 'multigraph p1_dm3'
        print 'graph_title gas usage'
        print 'graph_vlabel dm3/h'
        print 'graph_period hour'
        print 'graph_category P1'
        print 'dm3.label dm3/h'
        print 'dm3.type DERIVE'
        return 0
    if sys.argv[1] == 'autoconf':
        print 'yes'
        return 0
    return -1

if __name__ == '__main__':
    sys.exit(main())
