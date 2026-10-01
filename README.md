# YW3 to YWB1 Character Converter

A Python tool for converting Yo-kai Watch 3 character resources into formats
compatible with Yo-kai Watch Blasters.

The primary workflow converts the p00, p80, and p84 XC archives belonging to
one character and preserves their original filenames.

## Important Notice

This repository does not contain game ROMs, extracted game assets, XC samples,
or other copyrighted game data.

Users must provide their own input files. Do not upload or distribute
copyrighted game files through this repository, its issue tracker, or pull
requests.

## Features

- Converts a complete p00, p80, and p84 character XC set.
- Automatically finds all three XC archives from a directory or one selected
  member of the set.
- Preserves the original XC filenames.
- Converts character PRM files.
- Converts LKAT files.
- Converts `mtn3` to `mtn2`.
- Converts normal and special `mtninf2` entries.
- Converts `RES.bin` from `CHRC02` to `CHRC01` or `CHRC00`.
- Validates and copies formats shared by both games.
- Rebuilds converted files as XC/XPCK archives.
- Rejects unsupported structures instead of converting them silently.
- Does not overwrite input files.

Validated copy formats include:

- ATR
- MTR
- MBN
- XI
- TXP
- CMN
- SIL

## Requirements

- Python 3.10 or newer
- No third-party Python packages are required

## Quick Start

### Automatic Three-File Conversion

The converter requires the p00, p80, and p84 XC archives belonging to the same
character.

You may specify either:

- The directory containing all three XC archives.
- Any one of the three XC archives.

```powershell
python character_converter.py character-xc INPUT OUTPUT_DIRECTORY
```

Example using a directory:

```powershell
python character_converter.py character-xc input/y473000 converted/y473000
```

Example using one XC archive:

```powershell
python character_converter.py character-xc input/y473000/y473000_p00.xc converted/y473000
```

Both commands automatically locate and convert:

- `y473000_p00.xc`
- `y473000_p80.xc`
- `y473000_p84.xc`

The output filenames are identical to the input filenames.

## RES Version

`CHRC01` is used by default for all three output archives.

```powershell
--res-version 1
```

Use the following option to generate `CHRC00`:

```powershell
--res-version 0
```

## Overwriting Existing Output

Existing output is rejected by default. Use `--overwrite` only when the three
existing output files should be replaced.

```powershell
python character_converter.py character-xc INPUT OUTPUT_DIRECTORY --overwrite
```

## Individual and Two-Stage Commands

The converter also provides commands for individual formats, extracted p00 or
p80/p84 content, and XC repacking.

```powershell
python character_converter.py --help
python character_converter.py mtninf2 --help
python character_converter.py mtn3 --help
python character_converter.py prm --help
python character_converter.py lkat --help
python character_converter.py sil --help
python character_converter.py res --help
python character_converter.py p00-content --help
python character_converter.py p8-content --help
python character_converter.py pack-xc --help
python character_converter.py p00-xc --help
python character_converter.py p8-xc --help
```

## Documentation

- [Complete User Guide](USER_GUIDE.md)
- [Character XC Format Analysis](FORMAT_ANALYSIS.md)
- [Implementation Specification](IMPLEMENTATION_SPEC.md)

## Safety Behavior

- Input files are never overwritten.
- Existing output is rejected unless `--overwrite` is specified.
- Input p00, p80, and p84 names must belong to the same character.
- Unknown structures and invalid offsets produce descriptive errors.
- Output is staged before final replacement where appropriate.

Always keep backups of the original files.

## Known Limitations

- Only structures confirmed through the analyzed sample corpus are supported.
- A valid file containing an unknown structure may be rejected.
- A successful conversion does not guarantee correct behavior for every
  untested character.
- In-game testing is recommended after conversion.

## Verification Status

The converter has been tested with multiple paired YW3 and YWB1 character
samples. Converted p00, p80, and p84 archives have been verified in both an
emulator and on real hardware for the tested character assets.

## Contributing

Bug reports are welcome, but do not attach copyrighted game files.

When reporting a problem, include:

- The converter version.
- The command that was executed.
- The complete error message.
- The character XC filename.
- Whether the problem affects p00, p80, p84, or all three archives.
- A description of the observed in-game behavior.

## Disclaimer

This is an unofficial fan-made interoperability and research project.

This project is not affiliated with, endorsed by, or sponsored by LEVEL-5 Inc.

Yo-kai Watch and all related names and trademarks belong to their respective
owners.

## License

The original source code and documentation in this repository are available
under the MIT License. See [LICENSE.md](LICENSE.md).

The license applies only to the original code and documentation in this
repository. It does not apply to game data, trademarks, or third-party
material.
