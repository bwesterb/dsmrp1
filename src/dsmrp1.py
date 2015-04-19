import serial

import logging

# Reads DSMR3.0 P1 port

class InvalidTelegram(Exception):
    pass

_tst = lambda x: (2000+int(x[0:2]),
                  int(x[2:4]),            
                  int(x[4:6]),            
                  int(x[6:8]),            
                  int(x[8:10]))
_gas = lambda tst,sn,rp,z,id1,u1,m1: (_tst(tst), float(m1))
_unit = lambda x: float(x.split('*', 1)[0]) 
_tariff = lambda x: 'low' if x == '0002' else ('high' if x == '0001' else x)
_id = lambda x: x

OBIS = {
    '0-0:96.1.1': ('id', _id),
    '1-0:1.8.1': ('kWh', _unit),
    '1-0:1.8.2': ('kWh-low', _unit),
    '1-0:2.8.1': ('kWh-out', _unit),
    '1-0:2.8.2': ('kWh-out-low', _unit),
    '0-0:96.14.0': ('tariff', _tariff),
    '1-0:1.7.0': ('W', _unit),
    '1-0:2.7.0': ('W-out', _unit),
    '0-0:17.0.0': ('treshold', _unit),
    '0-0:96.3.10': ('switch', _id),
    '0-0:96.13.1': ('msg-numeric', _id),
    '0-0:96.13.0': ('msg-txt', _id),

    '0-1:24.1.0': ('type', _id),
    '0-1:96.1.0': ('id-gas', _id),
    '0-1:24.3.0': ('gas', _gas),
    '0-1:24.4.0': ('gas-switch', _id),
    }

class Meter(object):
    def __init__(self, device):
        self.serial = serial.Serial(device, 9600, bytesize=serial.SEVENBITS,
                            parity=serial.PARITY_EVEN)
        self.l = logging.getLogger(device)

    def read_telegram(self):
        telegram = {}

        # Wait for first line of telegram
        while True:
            line = self.serial.readline().strip().strip('\0')
            if not line.startswith('/'):
                self.l.debug('skipping line %s', repr(line))
                continue
            break

        if not len(line) >= 5:
            raise InvalidTelegram("Header line too short")
        telegram['header-marker'] = line[0:6]
        telegram['header-id'] = line[6:]

        # Read second (blank) line
        if self.serial.readline().strip() != '':
            raise InvalidTelegram('Second line should be blank')

        # Read data
        raw_lines = []
        while True:
            line = self.serial.readline().strip()
            if line == '!':
                break
            raw_lines.append(line)

        # Remove superfluous linebreaks
        lines = []
        for raw_line in raw_lines:
            if raw_line.startswith('(') and lines:
                lines[-1] += raw_line
                continue
            lines.append(raw_line)

        # Parse lines
        for line in lines:
            bits = line.split('(')
            obis = bits[0]
            args = []
            for bit in bits[1:]:
                if not bit.endswith(')'):
                    raise InvalidTelegram('Malformed argument')
                args.append(bit[:-1])
            if not obis in OBIS:
                self.l.warning('Unknown data object with OBIS %s', repr(obis))
                continue
            name, data_func = OBIS[obis]
            data = data_func(*args)
            telegram[name] = data

        return telegram


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    m = Meter('/dev/P1')
    while True:
        print m.read_telegram()
