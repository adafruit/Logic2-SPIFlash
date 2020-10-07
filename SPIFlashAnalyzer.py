# High Level Analyzer
# For more information and documentation, please go to https://support.saleae.com/extensions/high-level-analyzer-extensions

from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, StringSetting, NumberSetting, ChoicesSetting

import struct

DATA_COMMANDS = {0x03: "Read",
                 0x0b: "Fast Read",
                 0x02: "Page Program",
                 0x32: "Quad Page Program"}

CONTROL_COMMANDS = {
    0x06: "Write Enable",
    0x05: "Read Status Register",
    0x75: "Program Suspend"
}

# High level analyzers must subclass the HighLevelAnalyzer class.
class SPIFlash(HighLevelAnalyzer):
    # List of settings that a user can set for this High Level Analyzer.
    address_bytes = NumberSetting(min_value=1, max_value=4)
    min_address = NumberSetting(min_value=0)
    max_address = NumberSetting(min_value=0)
    decode_level = ChoicesSetting(choices=('Everything', 'Only Data', 'Only Errors', 'Only Control'))

    # An optional list of types this analyzer produces, providing a way to customize the way frames are displayed in Logic 2.
    result_types = {
        'error': {
            'format': 'Error!'
        },
        'control_command': {
            'format': '{{data.command}}'
        },
        'data_command': {
            'format': '{{data.command}} 0x{{data.address}}'
        }
    }

    def __init__(self):
        '''
        Initialize HLA.

        Settings can be accessed using the same name used above.
        '''
        self._start_time = None
        self._address_format = "{:0" + str(2*int(self.address_bytes)) + "x}"
        self._min_address = int(self.min_address)
        self._max_address = None
        if self.max_address:
            self._max_address = int(self.max_address)

    def decode(self, frame: AnalyzerFrame):
        '''
        Process a frame from the input analyzer, and optionally return a single `AnalyzerFrame` or a list of `AnalyzerFrame`s.

        The type and data values in `frame` will depend on the input analyzer.
        '''

        if frame.type == "enable":
            self._start_time = frame.start_time
            self._miso_data = bytearray()
            self._mosi_data = bytearray()
        elif frame.type == "result":
            if self._miso_data is None or self._mosi_data is None:
                print(frame)
                return
            self._miso_data.extend(frame.data["miso"])
            self._mosi_data.extend(frame.data["mosi"])
        elif frame.type == "disable":
            if not self._miso_data or not self._mosi_data:
                return
            command = self._mosi_data[0]
            frame_type = None
            frame_data = {"command": command}
            if command in DATA_COMMANDS:
                if len(self._mosi_data) < 1 + int(self.address_bytes):
                    frame_type = "error"
                else:
                    frame_type = "data_command"
                    frame_data["command"] = DATA_COMMANDS[command]
                    frame_address = 0
                    for i in range(int(self.address_bytes)):
                        frame_address <<= 8
                        frame_address += self._mosi_data[1+i]
                    if self.min_address > 0 and frame_address < self._min_address:
                        frame_type = None
                    elif self.max_address and frame_address > self.max_address:
                        frame_type = None
                    else:
                        frame_data["address"] = self._address_format.format(frame_address)
            else:
                if command in CONTROL_COMMANDS:
                    frame_data["command"] = CONTROL_COMMANDS[command]
                frame_type = "control_command"
            our_frame = None
            if frame_type:
                our_frame = AnalyzerFrame(frame_type,
                                          self._start_time,
                                          frame.end_time,
                                          frame_data)
            self._miso_data = None
            self._mosi_data = None
            if self.decode_level == 'Only Data' and frame_type == "control_command":
                return None
            if self.decode_level == 'Only Errors' and frame_type != "error":
                return None
            if self.decode_level == "Only Control" and frame_type != "control_command":
                return None
            return our_frame
        else:
            print(frame)
