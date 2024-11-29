# petscii-to-d64

Convert .c file from Marq's PETSCII editor to a D64 directory listing

## Rationale

This tool can be used for exporting the graphics and then e.g. imported as a Spindle trackmo dirart

## Usage

```
usage: petscii_to_d64.py [-h] [-f FRAME] [-l LINES] [-n LINE_LENGTH]
                         [-s OFFSET] [-o OUTPUT] [-i INPUT_DISK]
                         [--asm-dump [ASM_DUMP]]
                         [--asm-format {tass64,kickass}]
                         [--asm-truncate ASM_TRUNCATE]
                         [--cc1541-dump [CC1541_DUMP]] [--disk-name DISK_NAME]
                         [--disk-id DISK_ID] [--verbose]
                         filename

Convert dirart from Marq's PETSCII editor .c to .d64 file.

positional arguments:
  filename              dirart.c file

options:
  -h, --help            show this help message and exit
  -f, --frame FRAME     frame name (default: frame0000)
  -l, --lines LINES     number of lines
  -n, --line-length LINE_LENGTH
                        line length (default: 16)
  -s, --offset OFFSET   line offset (when converting art wider than 16 chars)
  -o, --output OUTPUT   output file (if omitted, only dump asm)
  -i, --input-disk INPUT_DISK
                        input disk image (if omitted, disk generated)
  --asm-dump [ASM_DUMP]
                        filename to dump filenames as assembly code (default:
                        <FILENAME>.s)
  --asm-format {tass64,kickass}
                        asm dump format (default: tass64)
  --asm-truncate ASM_TRUNCATE
                        truncate asm dump filenames to N characters (default:
                        16)
  --cc1541-dump [CC1541_DUMP]
                        filename to dump filenames as cc1541 code (default:
                        <FILENAME>.txt)
  --disk-name DISK_NAME
                        disk name
  --disk-id DISK_ID     disk id
  --verbose, -v         verbose output
```

## Example workflow

### Create the dir art

1. Create directory art with the latest [Marq's PETSCII editor](http://www.kameli.net/marq/?page_id=2717) or [my fork of it](https://github.com/ventti/petscii).
2. Use 'Dir Art' mode for editing.

### Convert the dir art

By default, the first frame `frame0000` in .c file is converted

```sh
python3 petscii_to_d64.py examples/example.c -o dirart.d64
```

or to specify the frame (for e.g. disk A and B sides)

```sh
python3 petscii_to_d64.py examples/example.c -f frame0001 -o dirart-1.d64
python3 petscii_to_d64.py examples/example.c -f frame0002 -o dirart-2.d64
```

See the option flags for more customization details.

### Import the dir art to Spindle

Replace `spin` with `/path/to/your/spin` as per need

```sh
spin -vv -a dirart.d64 -o disk.d64 script
```

Spindle 3.1 binaries from (spindle-3.1.zip)[https://hd0.linusakesson.net/files/spindle-3.1.zip] for Windows and Linux and a self-compiled macOS arm64 included for convenience

## Known issues and limitations

* Number of lines can't be more than in the frame. If you want a long dir art, concatenate the PETSCII frames first manually.
* Tested to support dir art sizes up to 136 lines
* Control characters gimmicks not (yet?) supported / tested
