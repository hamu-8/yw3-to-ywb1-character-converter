# YW3 to YWB1 Character Converter

A Python tool for downgrading Yo-kai Watch 3 (YW3) character XC resources for
Yo-kai Watch Blasters (YWB1).

Default mode strictly converts one character's complete p00/p80/p84 set.
Explicit `--copy-p00` mode instead preserves the original model XC and
converts the available motion slots. Both preserve the input filenames.

## Important Notice

This repository does not contain game ROMs, extracted game assets, XC samples,
or other copyrighted game data.

Users must provide their own input files. Do not upload or distribute
copyrighted game files through this repository, its issue tracker, or pull
requests.

## Features

- Strictly converts a complete p00/p80/p84 set by default.
- Provides equivalent `INPUT OUTPUT --auto` and `character-xc` workflows.
- With explicit `--copy-p00`, container-validates and copies the entire p00
  XC unchanged, while normally converting present p80/p84 files.
- Allows 1–3 available major files in copy mode; missing slots are not created.
- Discovers one character's major XC files from a directory or selected major
  file; non-major XC slots are ignored in both modes.
- Preserves the original XC filenames.
- Converts character PRM files.
- Converts LKAT files.
- Splits and converts supported MTN3/MTM3/IMM3 bundles to individual v2 files.
- Converts supported MTNINF2 special entries and ordinary MTMINF2/IMMINF2.
- Rebuilds animation/INF RES categories with their actual logical identities.
- Writes converted `RES.bin` as `CHRC01` or `CHRC00`; copied p00 is unchanged.
- Validates and copies formats shared by both games.
- Rebuilds converted files as XC/XPCK archives.
- Rejects unsupported structures in strict conversion rather than guessing
  their transformation or silently stripping data.
- Does not overwrite input files.

Internal formats validated and preserved in the strict model pipeline include:

- ATR
- MTR
- MBN
- XI
- TXP
- CMN
- SIL

This per-format validation differs from whole-p00 copy mode, which validates
the XPCK container only and does not validate or transform the model internals.

## Requirements

- Python 3.10 or newer
- No third-party Python packages are required

## Quick Start

### Default Strict Conversion

The converter requires the p00, p80, and p84 XC archives belonging to the same
character.

You may specify either:

- The directory containing all three XC archives.
- Any one of the three XC archives.

```powershell
python character_converter.py INPUT OUTPUT_DIRECTORY --auto
```

The existing subcommand form is equivalent:

```powershell
python character_converter.py character-xc INPUT OUTPUT_DIRECTORY
```

Example using a directory:

```powershell
python character_converter.py input/y473000 output/y473000 --auto
```

Example using one XC archive:

```powershell
python character_converter.py input/y473000/y473000_p00.xc output/y473000 --auto
```

Both commands automatically locate and convert:

- `y473000_p00.xc`
- `y473000_p80.xc`
- `y473000_p84.xc`

The output filenames are identical to the input filenames.

These examples run from the repository directory and use input files you must
provide. Discovery is not recursive. Directory input rejects major XCs from
different characters; selecting one major file restricts discovery to its
same-character siblings. p10/p20 and other non-major slots are neither converted
nor copied.

### Preserve p00 and Convert Available Motions

```powershell
python character_converter.py input/y473000 output/y473000_copy_p00 --auto --copy-p00
```

Equivalent long form:

```powershell
python character_converter.py character-xc input/y473000 output/y473000_copy_p00 --copy-p00
```

`--copy-p00` is an **always-copy policy**, not a fallback after a model conversion
error. It copies a present p00 even if strict conversion could have succeeded.

- A present p00 passes XPCK container validation, then its complete original
  archive bytes are copied. It is not internally converted or repacked.
- Present p80/p84 files still undergo normal strict conversion and repacking.
- Any existing same-character subset of 1–3 major files is allowed. A p00-only
  input produces one exact p00 copy; motion-only input converts those motions
  without creating p00. Missing archives are never synthesized.
- Internal p00 PRM/XI/MBN/RES structure and reference compatibility are not
  model-validated in this mode. A copied p00 can retain `CHRC02`.
- If the p00 container is invalid or any selected motion conversion fails,
  no new selected outputs are written. Existing outputs remain unchanged by
  that format error. Unsupported motions are never copied or stripped as a
  fallback.

The user reports that unmodified YW3 p00 can work in B1. This is user-provided
runtime evidence for offering the option, not new game verification of every
copied character. Verify model appearance, textures, attachments, and animation
behavior in your own target environment.

`--copy-p00` belongs to `character-xc` / the `--auto` shorthand; it does not change
standalone `p00-xc` or internal-format commands. Without the flag, all three
major files and strict p00 conversion are still required.

## RES Version

`CHRC01` is used by default for every **converted** RES. In normal mode this
applies to all three archives. In `--copy-p00` mode the selected version applies
only to converted p80/p84; p00 keeps its original RES bytes and version.

```powershell
--res-version 1
```

Use the following option to generate `CHRC00`:

```powershell
--res-version 0
```

## Overwriting Existing Output

Existing output is rejected by default. Use `--overwrite` only when the selected
existing output files should be replaced. It does not allow source overwriting
or bypass validation.

```powershell
python character_converter.py INPUT OUTPUT_DIRECTORY --auto --overwrite
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
- Unknown internal structures and invalid references are rejected in strict
  conversion. Explicit whole-p00 copying instead validates the container and
  preserves its internals without claiming conversion compatibility.
- All selected files are prepared before staged output begins; a normal format
  error cannot leave a newly written partial set.

An OS failure while replacing several files in an existing output directory is
not a filesystem transaction; keep backups independently of these checks.

Always keep backups of the original files.

## Known Limitations

- Strict internal conversion supports only structures established by the
  analyzed corpus; explicit p00 copying does not establish those model rules.
- A valid file containing an unknown internal structure may be rejected by
  strict conversion. Whole-p00 copy has the narrower container-only guarantee.
- A successful conversion or copy does not guarantee correct behavior for every
  untested character.
- In-game testing is recommended after conversion.

The following two motion archives remain unconvertible under the established
rules, including when `--copy-p00` is specified:

| XC filename | Problem internal file | Unsupported special form |
|---|---|---|
| `x611000_p80.xc` | `000.mtninf2` | Entry 2, descriptor 0: A=4, event `0x044E`, auxiliary value 0 |
| `x791000_p84.xc` | `000.mtninf2` | Entry 5, descriptor 0: A=16 |

Selecting either prevents writing the new selected set. The option changes
p00 handling only; it does not permit copying or deleting these motion events.

## Verification Status

The original paired character sample sets were strictly converted and confirmed
in an emulator and on real hardware. Later full-corpus format extensions are
structurally verified, not newly game-tested for every character.

### Historical Strict Audit — 2026-10-14

The supplied 2,949 major XC files produced 2,843 successful structural
conversions and verified repacks, with 106 unresolved cases:

| Slot | Successful strict conversions | Unresolved |
|---|---:|---:|
| p00 | 1,060 | 104 |
| p80 | 890 | 1 |
| p84 | 893 | 1 |

Of the earlier 637 failures, 531 were recovered. All 243 failed archives that
had same-name B1 counterparts were recovered. Successful structural conversion
does not establish new in-game compatibility.

The 104 p00 cases remain **unsupported internal-conversion cases**, not proof
that their unchanged source archives are impossible to transplant. Copy mode
does not claim that the missing internal downgrade rules have been solved.
The two motion cases above remain strict conversion failures in every mode.

### Copy-Mode Checks — 2026-10-15

All 104 historically unresolved p00 cases were exercised in memory: every p00
output exactly matched its original XC bytes, present motion outputs matched
normal conversion, and missing slots were not created. These comprised 103
p00-only sets and one complete trio (`y740000`). This check saved no new XC files
and was not a game test.

During development, 67 recovery/copy regression tests passed. The public bundle
does not include the development tests, tools, ROM fixtures, or generated JSON
reports. It contains the standalone converter, English documentation, license,
and ignore file only. No Japanese documentation or copyrighted game assets are
included.

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
