# This file is used to process section data generated by `objdump -s`
import re


class Section(object):
    """
    One Section of section table. contains info about section name, address and raw data
    """
    SECTION_START_PATTERN = re.compile("Contents of section (.+?):")
    DATA_PATTERN = re.compile("([0-9a-f]{4,8})")

    def __init__(self, name, start_address, data):
        self.name = name
        self.start_address = start_address
        self.data = data

    def __contains__(self, item):
        """ check if the section name and address match this section """
        if (item["section"] == self.name or item["section"] == "any") \
                and (self.start_address <= item["address"] < (self.start_address + len(self.data))):
            return True
        else:
            return False

    def __getitem__(self, item):
        """ 
        process slice. 
        convert absolute address to relative address in current section and return slice result
        """
        if isinstance(item, int):
            return self.data[item - self.start_address]
        elif isinstance(item, slice):
            start = item.start if item.start is None else item.start - self.start_address
            stop = item.stop if item.stop is None else item.stop - self.start_address
            return self.data[start:stop]
        return self.data[item]

    def __str__(self):
        return "%s [%08x - %08x]" % (self.name, self.start_address, self.start_address + len(self.data))

    __repr__ = __str__

    @classmethod
    def parse_raw_data(cls, raw_data):
        """
        process raw data generated by `objdump -s`, create section and return un-processed lines
        :param raw_data: lines of raw data generated by `objdump -s`
        :return: one section, un-processed lines
        """
        name = ""
        data = ""
        start_address = 0
        # first find start line
        for i, line in enumerate(raw_data):
            if "Contents of section " in line:  # do strcmp first to speed up
                match = cls.SECTION_START_PATTERN.search(line)
                if match is not None:
                    name = match.group(1)
                    raw_data = raw_data[i + 1:]
                    break
        else:
            # do some error handling
            raw_data = [""]  # add a dummy first data line

        def process_data_line(line_to_process):
            # first remove the ascii part
            hex_part = line_to_process.split("  ")[0]
            # process rest part
            data_list = cls.DATA_PATTERN.findall(hex_part)
            try:
                _address = int(data_list[0], base=16)
            except IndexError:
                _address = -1

            def hex_to_str(hex_data):
                if len(hex_data) % 2 == 1:
                    hex_data = "0" + hex_data  # append zero at the beginning
                _length = len(hex_data)
                return "".join([chr(int(hex_data[_i:_i + 2], base=16))
                                for _i in range(0, _length, 2)])

            return _address, "".join([hex_to_str(x) for x in data_list[1:]])

        # handle first line:
        address, _data = process_data_line(raw_data[0])
        if address != -1:
            start_address = address
            data += _data
            raw_data = raw_data[1:]
            for i, line in enumerate(raw_data):
                address, _data = process_data_line(line)
                if address == -1:
                    raw_data = raw_data[i:]
                    break
                else:
                    data += _data
        else:
            # do error handling
            raw_data = []

        section = cls(name, start_address, data) if start_address != -1 else None
        unprocessed_data = None if len(raw_data) == 0 else raw_data
        return section, unprocessed_data


class SectionTable(object):
    """ elf section table """

    def __init__(self, file_name):
        with open(file_name, "rb") as f:
            raw_data = f.readlines()
        self.table = []
        while raw_data:
            section, raw_data = Section.parse_raw_data(raw_data)
            self.table.append(section)

    def get_unsigned_int(self, section, address, size=4, endian="LE"):
        """
        get unsigned int from section table
        :param section: section name; use "any" will only match with address
        :param address: start address
        :param size: size in bytes
        :param endian: LE or BE
        :return: int or None
        """
        if address % 4 != 0 or size % 4 != 0:
            print("warning: try to access without 4 bytes aligned")
        key = {"address": address, "section": section}
        for section in self.table:
            if key in section:
                tmp = section[address:address+size]
                value = 0
                for i in range(size):
                    if endian == "LE":
                        value += ord(tmp[i]) << (i*8)
                    elif endian == "BE":
                        value += ord(tmp[i]) << ((size - i - 1) * 8)
                    else:
                        print("only support LE or BE for parameter endian")
                        assert False
                break
        else:
            value = None
        return value

    def get_string(self, section, address):
        """
        get string ('\0' terminated) from section table
        :param section: section name; use "any" will only match with address
        :param address: start address
        :return: string or None
        """
        value = None
        key = {"address": address, "section": section}
        for section in self.table:
            if key in section:
                value = section[address:]
                for i, c in enumerate(value):
                    if c == '\0':
                        value = value[:i]
                        break
                break
        return value