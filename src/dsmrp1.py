import serial
import crcmod.predefined

import logging

# Reads DSMR4.0 P1 port

class InvalidTelegram(Exception):
    pass

class BadChecksum(InvalidTelegram):
    pass


_tst = lambda x: (2000+int(x[0:2]),
                  int(x[2:4]),            
                  int(x[4:6]),            
                  int(x[6:8]),            
                  int(x[8:10]))
_gas = lambda tst,sn,rp,z,id1,u1,m1: (_tst(tst), float(m1))
_gas2 = lambda tst,m1: (_tst(tst), _unit(m1))
def _unit(x):
    amount, units = x.split('*',1)
    return float(amount) * UNITS[units]

_tariff = lambda x: 'low' if x == '0002' else ('high' if x == '0001' else x)
_id = lambda x: x
def _log(*args):
    ret = []
    for i in xrange(2, len(args), 2):
        ret.append((_tst(args[i]), _unit(args[i+1])))
    return ret


UNITS = {
    'kWh': 1,
    'kW': 1000,
    'W': 1,
    's': 1,
    'm3': 1,
    'A': 1,
    'V': 1}

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

    '1-3:0.2.8': ('P1-version', _id),
    '0-0:1.0.0': ('tst', _tst),
    '0-0:96.7.21': ('power-failures', int),
    '0-0:96.7.9': ('long-power-failures', int),

    '1-0:32.7.0': ('l1-voltage', _unit),

    '1-0:32.32.0': ('l1-voltage-sags', int),
    '1-0:52.32.0': ('l2-voltage-sags', int),
    '1-0:72.32.0': ('l3-voltage-sags', int),
    '1-0:32.36.0': ('l1-voltage-swells', int),
    '1-0:52.36.0': ('l2-voltage-swells', int),
    '1-0:72.36.0': ('l3-voltage-swells', int),

    '1-0:31.7.0': ('l1-current', _unit),
    '1-0:51.7.0': ('l2-current', _unit),
    '1-0:71.7.0': ('l3-current', _unit),
    '1-0:21.7.0': ('l1-power', _unit),
    '1-0:41.7.0': ('l2-power', _unit),
    '1-0:61.7.0': ('l3-power', _unit),
    '1-0:22.7.0': ('l1-power-out', _unit),
    '1-0:42.7.0': ('l2-power-out', _unit),
    '1-0:62.7.0': ('l3-power-out', _unit),
    '0-1:24.2.1': ('gas', _gas2),
    '1-0:99.97.0': ('power-failures-log', _log),
    }

class Meter(object):
    def __init__(self, device):
        self.serial = serial.Serial(device, 115200, bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
        self.l = logging.getLogger(device)
        self.crc = crcmod.predefined.mkPredefinedCrcFun('crc16')

    def _read_telegram(self):
        telegram = {}
        raw_lines = []

        # Wait for first line of telegram
        while True:
            line = self.serial.readline()
            #line = self.serial.readline().strip().strip('\0')
            if not line.startswith('/'):
                self.l.debug('skipping line %s', repr(line))
                continue
            break

        checksum_body = line
        
        if not len(line) >= 5:
            raise InvalidTelegram("Header line too short")
        telegram['header-marker'] = line[0:6]
        telegram['header-id'] = line[6:].strip()

        # Read second (blank) line
        line = self.serial.readline()
        if line.strip() != '':
            raise InvalidTelegram('Second line should be blank')
        checksum_body += line

        # Read data
        while True:
            line = self.serial.readline()
            if line.startswith('!'):
                break
            checksum_body += line
            raw_lines.append(line.strip())

        # Check CRC
        checksum1 = self.crc(checksum_body + '!')
        checksum2 = int(line[1:].strip(), 16)
        if checksum1 != checksum2:
            self.l.debug('Checksum mismatch')
            raise BadChecksum

        return raw_lines, telegram

    def read_telegram(self):
        while True:
            try:
                raw_lines, telegram = self._read_telegram()
                break
            except BadChecksum:
                pass

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
                self.l.warning('Unknown data object with OBIS %s and value %s',
                            repr(obis), repr(args))
                continue
            name, data_func = OBIS[obis]
            data = data_func(*args)
            telegram[name] = data

        return telegram


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    m = Meter('/dev/P1')
    while True:
        pairs = m.read_telegram().items()
        pairs.sort(key=lambda x: x[0])
        colwidth = max([len(k) for k, v in pairs])
        for k, v in pairs:
            print k.ljust(colwidth), v
