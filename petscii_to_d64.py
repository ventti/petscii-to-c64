# Convert dirart from Marq's PETSCII editor .c to a dummy .d64 file.
#
# Generates a bare-minimum .d64 file just enough to hold the directory entries.
# Ref: http://unusedino.de/ec64/technical/formats/d64.html
#
# by Vent/EXTEND 2024
#
import sys
import re
import string
import argparse

TRACK_18 = 0x16500  # directory track
SECTORS = [1, 4, 7, 10, 13, 16, 2, 5, 8, 11, 14, 17, 3, 6, 9, 12, 15, 18]  # sector interleaving

ASM_DUMP_TEMPLATE = {
    'tass64': '{label}:   .byte {name} ; {comment}',
    'kickass': '{label}:  .byte {name} // {comment}'
}

def screen_to_petscii(c):
    if c >= 0 and c <= 0x1f:
        p = c + 0x40
    elif c == 0xa0: # hack: allow line end
        p = c
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
    parser.add_argument('-s', '--offset', type=int, default=0, help='line offset (when converting art wider than 16 chars)')
    parser.add_argument('-o', '--output', help='output file (if omitted, only dump asm)', default=None)
    parser.add_argument('-i', '--input-disk', help='input disk image (if omitted, disk generated)', default=None)
    parser.add_argument('--asm-dump', help='filename to dump filenames as assembly code (default: <FILENAME>.s)', nargs="?", const="", default=None)
    parser.add_argument('--asm-format', help='asm dump format (default: tass64)', choices=['tass64', 'kickass'], default='tass64')
    parser.add_argument('--asm-truncate', help='truncate asm dump filenames to N characters (default: 16)', type=int, default=16)
    parser.add_argument('--cc1541-dump', help='filename to dump filenames as cc1541 code (default: <FILENAME>.txt)', nargs="?", const="", default=None)
    parser.add_argument('--disk-name', help='disk name', default=None)
    parser.add_argument('--disk-id', help='disk id', default=None)
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

def update_dir(track_18, filenames, disk_name=None, disk_id=None):
    # to bytearray
    log(f"Updating the directory with {len(filenames)} entries")
    ns = 1
    this_sector = SECTORS[0]
    next_sector = SECTORS[ns]
    # next_track = 18
    original_header = track_18[0:256]
    hex_dump(original_header, title="Original header")
    track_18[0:256] = update_dir_header(original_header, disk_name, disk_id)
    hex_dump(track_18[0:256], title="Updated header")
    # files in chunks of 8
    for i, _ in enumerate(filenames):
        if i % 8 == 0:
            offset = 256 * this_sector
            sector = track_18[offset:offset+256]
            sector = update_dir_sector(next_sector, filenames[i:i + 8], sector)
            track_18[offset:offset+256] = sector
            try:
                ns += 1
                this_sector = next_sector
                next_sector = SECTORS[ns]
            except IndexError:
                break
            # next_track = 18
    #original_track_18_data.ljust(256 * 19, b'\x00')  # pad track
    return track_18

def is_zeros(data):
    for b in data:
        if b != 0:
            return False
    return True

def generate_dir(track_18_data, filenames, disk_name, disk_id):
    log(f"Generating the directory with {len(filenames)} entries")
    ns = 1
    this_sector = SECTORS[0]
    next_sector = SECTORS[ns]
    # next_track = 18
    if track_18_data is None:
        track_18_data = bytearray([0x00] * 256 * 19)
    track_18_data[0:256] = generate_dir_header(track_18_data[0:256], disk_name=disk_name, disk_id=disk_id)

    # files in chunks of 8
    for i, filename in enumerate(filenames):
        if i % 8 == 0:
            offset = 256 * this_sector
            sector = track_18_data[offset:offset+256]
            sector = generate_dir_sector(sector, next_sector, filenames[i:i + 8])
            track_18_data[offset:offset+256] = sector
            try:
                ns += 1
                this_sector = next_sector
                next_sector = SECTORS[ns]
            except IndexError:
                break
            # next_track = 18
    track_18_data.ljust(256 * 19, b'\x00')  # pad track
    return track_18_data

def update_dir_header(header, disk_name=None, disk_id=None):
    if disk_name is not None:
        disk_name = bytearray(disk_name.encode('ascii'))
        header[0x90:0xA0] = disk_name.ljust(16, b'\xA0')
    if disk_id is not None:
        disk_id = bytearray(disk_id.encode('ascii'))
        header[0xA2:0xA4] = disk_id
    return header

def generate_dir_header(header, disk_name, disk_id):
    if is_zeros(header):
        header[0:2] = b'\x12\x01'
        header[2] = 0x41
        header[0x90:0xA0] = b'\xA0' * 16
        header[0xA0:0xA4] = b'\xA0\xA0\xA0\xA0\xA0'
        header[0xA5:0xA7] = b'\x32\x41'
        header[0xA7:0xAA] = b'\xA0\xA0\xA0'
    header = update_dir_header(header, disk_name, disk_id)
    return header

def update_dir_sector(next_sector, filenames, sector_data):
    hex_dump(sector_data, title="Sector data (old)")
    for i, filename in enumerate(filenames):
        entry = sector_data[i * 32:i * 32 + 32]
        # jos filename löytyy ja sektorissa on siinä kohtaa 0x00 * 32, lisää kaikki kentät.
        entry_data = update_entry(entry, filename)
        sector_data[i * 32:i * 32 + 32] = entry_data
        #next_sector = 0x00  # nonzero only for first entry
        #next_track = 0x00  # nonzero only for first entry
    hex_dump(sector_data, title="Sector data (updated)")
    return sector_data

def generate_dir_sector(sector, next_sector, filenames):
    next_track = 18
    for i, filename in enumerate(filenames):
        entry_data = sector[i*32:i*32+32]
        entry_data = generate_entry(entry_data,next_track, next_sector, filename)
        sector[i * 32:i * 32 + 32] = entry_data
        next_sector = 0x00  # nonzero only for first entry
        next_track = 0x00  # nonzero only for first entry
    return sector

def generate_entry(entry, next_track, next_sector, filename):
    #entry = bytearray([0x00] * 32)
    entry[0x00] = next_track
    entry[0x01] = next_sector
    if is_zeros(entry):
        entry[0x02] = 0x81  # file type
        entry[0x03] = 0x11  # file track
        entry[0x04] = 0x00  # file sector
        entry[0x05:0x15] = bytearray([0xA0] * 16)  # file size
        entry[0x1e] = 0x01  # zero size
        entry[0x1f] = 0x00  # zero size
    else:
        hex_dump(entry,title=f"Entry data (orig)")
    entry = update_entry(entry, filename)
    hex_dump(entry, title=f"Entry data")
    return entry

def update_entry(entry, filename):
    entry[0x05:0x15] = filename.ljust(16, b'\xA0')  # file size
    return entry

def hex_dump(data, linelen=16, printable=None, substitute='?', title=None):
    if title is not None:
        log(title)
        log('=' * len(title))
    if printable is None:
        printable = string.digits + string.ascii_letters + string.punctuation + " "
        
    if isinstance(data, bytearray):
        data = [data]  # Convert single bytearray to a list for uniform handling

    i = 0
    for chunk in data:
        j = 0
        while j < len(chunk):
            subchunk = chunk[j:j + linelen]
            datahex = ''
            decoded = ''
            
            for ch in subchunk:
                datahex += f"{ch:02x} "
                decoded += chr(ch) if chr(ch) in printable else substitute
                
            datahex += f" | {decoded} |"

            log(f"{i:04x}:{(i + linelen):04x} : {datahex}")
            
            i += linelen
            j += linelen

def main():
    args = parse_args()
    
    global verbose
    verbose = args.verbose
    output = args.output
    asm_dump = args.asm_dump
    cc1541_dump = args.cc1541_dump

    if asm_dump is None:
        if args.filename.lower().endswith(".c"):
            asm_dump = args.filename[:-2] + ".s"
        else:
            asm_dump = args.filename + ".s"

    if cc1541_dump is None:
        if args.filename.lower().endswith(".c"):
            cc1541_dump = args.filename[:-2] + ".txt"
        else:
            cc1541_dump = args.filename + ".txt"

    asm_truncate = args.asm_truncate

    with open(args.filename, 'rt') as fp:
        c = fp.read()
    meta = parse_petscii_c_meta(c)
    c_size = meta["width"] * meta["height"]
    data = parse_petscii_c(c, c_size).get(args.frame)

    for i in range(len(data)):
        data[i] = screen_to_petscii(data[i])
    
    if output:
        log(f"Convert input: {args.filename}, "
            f"Data length: {len(data)}, "
            f"N of lines: {args.lines} Line length: {args.line_length}, "
            f"Output: {output}")

    linelen = args.line_length
    offset = args.offset

    if args.lines is not None:
        max_lines = args.lines
    else:
        max_lines = meta["height"]

    filenames = []

    for line in range(max_lines):
        start_offset = line * meta["width"] + offset
        end_offset = start_offset + linelen
        filename = data[start_offset:end_offset]
        filenames.append(filename)

    hex_dump(filenames, linelen=linelen)

    i = 0

    if args.input_disk:
        with open(args.input_disk, 'rb') as fp:
            d64 = bytearray(fp.read())
    else:
        d64 = bytearray([0x00] * 174848)

    track_18 = d64[TRACK_18:TRACK_18 + 256 * 19]
    track_18 = generate_dir(track_18, filenames, args.disk_name, args.disk_id)
    
    names = []  # another hack for duplicate filenames in asm dump for Krill's loader
    if cc1541_dump:
        with open(cc1541_dump, 'w') as fp:
            for i, filename in enumerate(filenames):
                name = ''.join([f'#{ch:02x}' for ch in filename]).split('#a0')[0]
                fp.write(f"{name}\n")
        log(f"Dumped filenames as cc1541 code to {cc1541_dump}")
    if asm_dump:
        with open(asm_dump, 'w') as fp:
            for i, filename in enumerate(filenames):
                label = f"fname{i:02x}"
                # cut filename at 0xa0
                filename = filename.split(b'\xa0')[0]
                fnamebytes = filename[:asm_truncate]
                name = ','.join([f"${ch:02x}" for ch in fnamebytes]) + ",0"
                comment=''.join([chr(ch) if ch >= 0x20 and ch <= 0x7f else '.' for ch in filename])
                if name in names:
                    orig = names.index(name)
                    comment += f" WARNING: duplicate of fname{orig:02x}"
                names.append(name)
                asm_line = ASM_DUMP_TEMPLATE[args.asm_format].format(label=label, name=name.ljust(asm_truncate * 4 + 1), comment=comment)
                fp.write(asm_line + '\n')
        log(f"Dumped filenames as assembly code to {asm_dump}")

    if output:
        d64[TRACK_18:TRACK_18 + len(track_18)] = track_18
        with open(output, 'wb') as fp:
            fp.write(d64)
        log(f"Wrote filenames to {output}")
    log("Done.")

if __name__ == '__main__':
    main()
