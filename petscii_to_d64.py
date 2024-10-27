# Convert dirart from Marq's PETSCII editor .c to a dummy .d64 file.
#
# Generates a bare-minimum .d64 file just enough to hold the directory entries.
#
# by Vent/EXTEND 2024
#
import sys
import re
import string
import argparse

TRACK_18 = 0x16500  # directory track
SECTORS = [1, 4, 7, 10, 13, 16, 2, 5, 8, 11, 14, 17, 3, 6, 9, 12, 15, 18]  # sector interleaving

def screen_to_petscii(c):
    if c >= 0 and c <= 0x1f:
        p = c + 0x40
    elif c >= 0x20 and c <= 0x3f:
        p = c
    elif c >= 0x40 and c <= 0x5d:
        p = c + 0x80
    elif c == 0x5e:
        p = 0xff
    elif c == 0x5f:
        p = 0x7f
    elif c == 0x95:
        p = 0xdf
    elif c >= 0x60 and c <= 0x7f:
        p = c + 0x80
    elif c >= 0x80 and c <= 0xbf:
        p = c - 0x80
    elif c >= 0xc0 and c <= 0xff:
        p = c - 0x40
    else:
        log(f"WARNING: Directory does not support PETSCII screen code 0x{c:02x}")
        p = 0x40 # @
    return p


def parse_args():
    parser = argparse.ArgumentParser(description='Convert dirart from Marq\'s PETSCII editor .c to .d64 file.')
    parser.add_argument('filename', help='dirart.c file')
    parser.add_argument('-f', '--frame', help='frame name (default: frame0000)', default='frame0000')
    parser.add_argument('-l', '--lines', type=int, default=None, help='number of lines')
    parser.add_argument('-n', '--line-length', type=int, default=16, help='line length (default: 16)')
    parser.add_argument('-o', '--output', help='output file', required=True)
    parser.add_argument('--disk-name', help='disk name', default='DISKNAME')
    parser.add_argument('--disk-id', help='disk id', default='ID')
    parser.add_argument('--verbose', '-v', help='verbose output', action='store_true')
    return parser.parse_args()


def log(*args, **kwargs):
    if verbose:
        print(*args, file=sys.stderr, **kwargs)


def parse_petscii_c(c, chars):
    # Pattern to match variable name and array contents
    re_c_line_comment = re.compile(r"//.*$", re.MULTILINE)
    re_c_comment = re.compile(r"/\*.+\*/", re.DOTALL)
    re_image = re.compile(r"unsigned\s+char\s+(\w+)\[\]\s*=\s*\{([^\}]*)\};", re.DOTALL)

    # Remove comments
    c = re_c_line_comment.sub("", c)
    c = re_c_comment.sub("", c)

    bytearrays_dict = {}

    matches = re_image.findall(c)

    for match in matches:
        frame_name = match[0]
        array_contents = match[1]
        log(f"frame_name: {frame_name}, array_contents: {array_contents}")
        # Split the contents into integers and create a bytearray
        array_values = [int(num.strip()) for num in array_contents.split(',') if num.strip()]

        if chars < len(array_values):
            # omit the screen, background and the color values
            array_values = array_values[2:2 + chars]
        bytearrays_dict[frame_name] = bytearray(array_values)
    return bytearrays_dict

def parse_petscii_c_meta(c):
    # Regular expression pattern to match the META comment structure
    pattern = re.compile(r"// META:\s*(\d+)\s+(\d+)\s+(\w+)\s+(\w+)")

    # Split the input string into lines and search for a META comment
    for line in c.splitlines():
        match = pattern.search(line)
        if match:
            # Extract the values from the match and assign them to respective keys
            meta = {
                "width": int(match.group(1)),
                "height": int(match.group(2)),
                "type": match.group(3),
                "charset": match.group(4)
            }
            log(f"{meta}")
            return meta

def generate_dir(filenames, disk_name, disk_id):
    ns = 1
    this_sector = SECTORS[0]
    next_sector = SECTORS[ns]
    # next_track = 18
    track_18_data = bytearray([0x00] * 256 * 19)
    track_18_data[0:256] = generate_dir_header(disk_name, disk_id)

    # files in chunks of 8
    for i, filename in enumerate(filenames):
        if i % 8 == 0:
            sector = generate_dir_sector(next_sector, filenames[i:i + 8])
            offset = 256 * this_sector
            track_18_data[offset:offset+256] = sector
            try:
                ns += 1
                this_sector = next_sector
                next_sector = SECTORS[ns]
            except:
                break
            # next_track = 18
    track_18_data.ljust(256 * 19, b'\x00')  # pad track
    return track_18_data

def generate_dir_header(disk_name, disk_id):
    header = bytearray([0x00] * 256)
    header[0:2] = b'\x12\x01'
    header[2] = 0x41
    header[0x90:0xA0] = disk_name.ljust(16, b'\xA0')
    header[0xA0:0xA2] = b'\xA0\xA0'
    header[0xA2:0xA4] = disk_id
    header[0xA4] = 0xA0
    header[0xA5:0xA7] = b'\x32\x41'
    header[0xA7:0xAA] = b'\xA0\xA0\xA0'
    return header

def generate_dir_sector(next_sector, filenames):
    next_track = 18
    sector_data = bytearray([0x00] * 256)
    for i, filename in enumerate(filenames):
        entry_data = generate_entry(next_track, next_sector, filename)
        sector_data[i * 32:i * 32 + 32] = entry_data
        next_sector = 0x00  # nonzero only for first entry
        next_track = 0x00  # nonzero only for first entry
    return sector_data

def generate_entry(next_track, next_sector, filename):
    # if len(filename) < 16:
    #    filename += [0xA0] * (16 - len(filename))
    entry = bytearray([0x00] * 32)
    entry[0x00] = next_track
    entry[0x01] = next_sector
    entry[0x02] = 0x81  # file type
    entry[0x03] = 0x11  # file track
    entry[0x04] = 0x00  # file sector
    entry[0x05:0x15] = filename.ljust(16, b'\xA0')  # file size
    entry[0x1e] = 0x01  # zero size
    entry[0x1f] = 0x00  # zero size
    return entry

def main():
    args = parse_args()
    global verbose
    verbose = args.verbose
    with open(args.filename, 'rt') as fp:
        c = fp.read()
    meta = parse_petscii_c_meta(c)
    c_size = meta["width"] * meta["height"]
    data = parse_petscii_c(c, c_size).get(args.frame)

    for i in range(len(data)):
        data[i] = screen_to_petscii(data[i])
    if args.output:
        output = args.output
        closefd = True
        output_name = args.output
    log(f"Convert input: {args.filename}, "
        f"Data length: {len(data)}, "
        f"N of lines: {args.lines} Line length: {args.line_length}, "
        f"Output: {output_name}")

    linelen = args.line_length

    printable = string.digits + string.ascii_letters + string.punctuation + " "

    entries = []
    i = 0
    while i < len(data):
        filename = data[i:i + linelen]
        datahex = ''
        decoded = ''
        for ch in filename:
            datahex += f"{ch:02x} "
            if chr(ch) in printable:
                decoded += chr(ch)
            else:
                decoded += '?'

        entries.append(filename)  # .to_bytes(1))
        # fp.write(ch.to_bytes(1))#, byteorder='big'))
        # fp.write(b'\n')
        datahex += f" | {decoded} |"
        log(f"{i:04x}:{(i + linelen):04x} : {datahex}")
        i += linelen
        if args.lines and len(entries) >= args.lines:
            break
    # to bytearray
    disk_name = bytearray(args.disk_name.encode('ascii'))
    disk_id = bytearray(args.disk_id.encode('ascii'))
    track_18 = generate_dir(entries, disk_name, disk_id)

    d64 = bytearray([0x00] * 174848)
    d64[TRACK_18:TRACK_18 + len(track_18)] = track_18

    with open(output, 'wb') as fp:
        fp.write(d64)

    log("Done.")

if __name__ == '__main__':
    main()