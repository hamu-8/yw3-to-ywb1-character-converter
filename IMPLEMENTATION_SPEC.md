# YW3 to YWB1 Character XC Converter Implementation Specification

## 1. Purpose of This Document

This document specifies the external behavior, internal design, conversion pipelines, validation rules, input/output policy, error handling, and test strategy of `character_converter.py`, which converts Yo-kai Watch 3 (YW3) character XC archives for use in Yo-kai Watch Blasters (YWB1).

For the evidence behind the binary rules, sample counts, field interpretations, and the distinction between confirmed and unknown details, see the format-analysis document:

- [FORMAT_ANALYSIS.md](./FORMAT_ANALYSIS.md)

This specification records how those findings are implemented. End-user commands and workflows are documented separately:

- [USER_GUIDE.md](./USER_GUIDE.md)

The implementation is contained in:

```text
character_convert/character_converter.py
```

## 2. Scope

### 2.1 Supported XC Slots

The converter handles three archives per character.

| Slot | Contents | Main operation |
|---|---|---|
| `p00` | Model-related resources | Convert PRM, LKAT, and RES; validate and preserve the remaining model formats |
| `p80` | Motion-related resources | Convert MTN3, MTNINF2, and RES; validate and preserve CMN |
| `p84` | Motion-related resources | Convert MTN3, MTNINF2, and RES; validate and preserve CMN |

XC names are expected to combine a character base name and slot.

```text
<character_base>_p00.xc
<character_base>_p80.xc
<character_base>_p84.xc
```

Example:

```text
y473000_p00.xc
y473000_p80.xc
y473000_p84.xc
```

### 2.2 Supported Internal Formats

| YW3 input | Output or handling |
|---|---|
| `mtn3` | Convert to `mtn2` |
| `mtninf2` | Split and convert into multiple `mtninf` files |
| `prm` | Convert to YWB1-compatible PRM |
| `lkat` | Change the YWB1 compatibility value |
| `RES.bin` | Rebuild `CHRC02` as `CHRC00` or `CHRC01` |
| `atr` | Preserve after structural validation |
| `mtr` | Preserve after MTR/LUTC validation |
| `mbn` | Preserve after structural validation |
| `sil` | Preserve after XCSL/CMBC validation |
| `xi` | Preserve after IMGC00/ETC1 validation |
| `txp` | Preserve after structural validation |
| `cmn` | Preserve after type and variable-length validation |

### 2.3 Out of Scope

The current implementation does not:

- Convert a non-character XC as though it were a character archive.
- Guess the meaning of slots other than `p00`, `p80`, and `p84`.
- Approximate unknown ATR layouts, XI image formats, CMN types, or MTN descriptor types.
- Import YWB1-side revisions of models, textures, LUTs, or animation content into the YW3 asset.
- Install files into a ROM, rebuild a ROM, or transfer output to an emulator or console.
- Create a persistent extracted `_content` directory during raw-XC conversion.
- Require whole-file byte identity with every official YWB1 archive when asset content or compression differs legitimately.

## 3. Implementation Goals

The implementation satisfies these requirements.

1. Accept a raw YW3 XC directly.
2. Convert `p00`, `p80`, and `p84` individually or as one three-file set.
3. Preserve each input XC filename in the output directory.
4. Require the user to select only the output directory and, when necessary, the RES version.
5. Refuse to overwrite existing output by default.
6. Reject unknown structures instead of guessing a transformation.
7. Structurally validate even the internal files that are copied without modification.
8. Complete all internal conversion before beginning final output writes.
9. Re-extract each newly packed XPCK and verify exact equality with the converted internal-file set.
10. Keep the character and effect converter implementations separate while reusing the established binary knowledge.

## 4. Runtime and Dependencies

### 4.1 Python Version

Python 3.10 or later is required. The implementation uses:

- `X | None` union syntax.
- Built-in generic types such as `list[...]` and `dict[...]`.
- `Path.is_relative_to`.
- `Path.unlink(missing_ok=True)`.

### 4.2 External Packages

No external Python package is required. Only the standard library is used.

| Module | Purpose |
|---|---|
| `argparse` | CLI parsing |
| `binascii` | CRC32 |
| `collections.deque` | LZ10 candidate tracking |
| `math` | Finite-float validation |
| `os` | Temporary file handling and replacement |
| `shutil` | Staging-directory cleanup |
| `struct` | Little-endian integer and float access |
| `tempfile` | Temporary files and directories |
| `dataclasses` | Parsed binary structures |
| `pathlib` | Path handling |

### 4.3 Endianness

Unless stated otherwise, binary integers and floating-point values are read and written as little-endian.

## 5. Architecture

The implementation is divided into layers by the size of the operation.

```text
CLI
 └─ File/directory I/O wrappers
     ├─ Three-XC set conversion
     ├─ p00 or p80/p84 XC conversion
     ├─ Extracted internal-file set conversion
     └─ Single-file conversion
         └─ Pure bytes-based conversion and validation functions
             ├─ XPCK extraction/repacking
             ├─ Level-5 decompression/LZ10 compression
             └─ Per-format conversion and validation
```

### 5.1 Bytes Layer

Core functions accept `bytes` or `dict[str, bytes]` and return converted data without depending on the filesystem.

This design:

- Tests binary rules without disk I/O.
- Converts raw XC archives without persistent intermediate files.
- Allows the same logic to be reused by individual commands, batch commands, and a future GUI.

### 5.2 File I/O Layer

Wrappers validate input paths, output paths, extensions, and overwrite conditions, then call the bytes layer. Output is staged through a temporary file or directory.

### 5.3 CLI Layer

The CLI parses subcommands and calls the appropriate I/O wrapper. It prints a result summary on success and a user-facing error beginning with `Error:` on failure.

## 6. Shared Error Design

### 6.1 `ConversionError`

`ConversionError` represents an input that does not match a supported binary layout or a request that violates output-safety conditions.

The helper `require(condition, message)` raises `ConversionError(message)` when its condition is false.

### 6.2 CLI Exit Codes

| State | Exit code |
|---|---:|
| Success | `0` |
| Conversion error or OS I/O error | `1` |
| `argparse` argument error | `2` |

The top-level CLI catches `ConversionError` and `OSError` and prints a concise message instead of a stack trace.

### 6.3 Unknown Structures

The converter does not zero unknown fields, round them to a nearby known value, or silently drop unsupported files. It stops as soon as input falls outside the analyzed structures.

This is intended to prevent a misleading “successful conversion” whose only observable result in game is a missing model or animation.

## 7. Binary Helpers

| Function | Responsibility |
|---|---|
| `u16(data, offset)` | Bounds-checked little-endian u16 read |
| `u32(data, offset)` | Bounds-checked little-endian u32 read |
| `p16(value)` | Encode little-endian u16 |
| `p32(value)` | Encode little-endian u32 |
| `crc32(raw)` | Calculate unsigned 32-bit CRC32 |

CRC32 is used to verify filenames, RES strings, node names, and other references. The result is normalized to `0..0xFFFFFFFF`.

## 8. Level-5 Compression

### 8.1 Decompression

`level5_decompress` interprets the first u32 as:

```text
kind        = header & 7
output_size = header >> 3
```

Supported kinds are:

| Kind | Format | Main uses |
|---:|---|---|
| `1` | LZ10 | Filename tables, RES, converted MTN2/MTNINF, MTR metadata, XI image data |
| `2` | Huffman4 | Some RES files, XI tile tables, LUTC |
| `3` | Huffman8 | Some YW3 MTN3 files |
| `4` | RLE | LUTC |

Each decoder validates source termination, reference distance, Huffman tree references, and final output size. Unknown kinds are rejected.

### 8.2 Fast LZ10 Encoder

`level5_lz10_compress` is used for the comparatively large rebuilt MTN2 and MTNINF blocks.

- Maximum reference distance is `0x1000`.
- Maximum match length is 18 bytes.
- Recent positions with the same first three bytes are stored in a `deque`.
- At most 64 candidates are tested at each position.
- The output is a deterministic greedy stream, optimized for practical speed rather than globally optimal size.

### 8.3 Canonical LZ10 Encoder

`level5_lz10_compress_canonical` is used for the XPCK compressed filename table and `RES.bin`.

- Candidates are examined from farthest to nearest within the search window.
- An equal-length match does not replace the current choice.
- This reproduces the match selection observed in official XC archives.
- Exhaustive search is acceptable because it is limited to the small name table and RES.

Separating “valid and fast LZ10” from “official-layout-compatible LZ10” preserves MTN conversion speed while maximizing XPCK reproducibility.

## 9. XPCK Extraction

### 9.1 `unpack_xpck_archive`

The function accepts an entire XC as `bytes` and returns:

```python
dict[str, bytes]
```

The returned `RES.bin` is Level-5-decompressed. Every other entry is returned as its logical XPCK payload.

### 9.2 Validation

The extractor requires all of the following:

- `XPCK` magic.
- File count from 1 through 4095.
- Header index-bit count consistent with file count.
- A 12-byte information record for every file.
- Ordered, non-overlapping information, name, and data regions.
- Data-region end equal to archive end.
- A valid compressed filename table.
- Information records in strict filename-CRC32 order.
- In-range, NUL-terminated names.
- Matching filename CRC32 values.
- Unique, UTF-8 filenames.
- No `.`, `..`, path separator, or drive separator in a name.
- Every file payload inside the data region.
- Non-overlapping file intervals.
- Exactly `4 - (size % 4)` zero bytes after each payload.
- Presence of `RES.bin`.
- Expanded RES magic `CHRC00`, `CHRC01`, or `CHRC02`.

Even a payload already aligned to four bytes receives four padding bytes. This differs from conventional `(-size) % 4` alignment.

## 10. XPCK Repacking

### 10.1 `pack_xpck_files`

This function accepts a flat `dict[str, bytes]` and returns deterministic XPCK `bytes`.

### 10.2 Input Conditions

- One through 4095 files.
- Every name is a direct-child filename, not a path.
- No NUL in the UTF-8 name.
- No CRC32 collision between names.
- `RES.bin` exists.
- `RES.bin` is uncompressed `CHRC00` or `CHRC01`.
- No `.mtn3`, `.mtm3`, `.imm3`, `.mtninf2`, `.mtminf2`, or `.imminf2` remains.

### 10.3 Construction

1. Sort filenames by UTF-8 bytes.
2. Reject CRC32 collisions.
3. Build the NUL-terminated filename table.
4. Canonical-LZ10-compress the table and zero-pad it to a four-byte boundary.
5. Canonical-LZ10-compress `RES.bin`.
6. Place payloads in filename order.
7. Add `4 - (size % 4)` zero bytes after each payload.
8. Build the information table in filename-CRC32 order.
9. Build the 20-byte XPCK header.
10. Extract the completed archive with `unpack_xpck_archive`.
11. Require the extracted result to equal the input internal-file set exactly.

### 10.4 Size Limits

- Individual file size fits in 24 bits.
- Data-relative offset divided by four fits in 24 bits.
- Name-table offset fits in 16 bits.
- Expanded name table is at most 65536 bytes.
- Compressed name-table length divided by four and major table offsets divided by four fit in 16 bits.

## 11. MTN3 to MTN2

### 11.1 Conversion Function

```python
convert_mtn3(data: bytes) -> bytes
```

### 11.2 Input Validation

- File is at least `0x64` bytes.
- Magic is `XMTN`.
- Four descriptor-category counts can be read safely.
- Hash count fits the 16-bit pointer table.
- A Level-5 block exists after the descriptor table.
- The expanded block contains the hash table and four track records.
- Used-data length at `u32@0x10` is within the expanded block.
- Fourth value of every 16-byte descriptor is zero.
- Flag, frame, and value offsets lie within the used-data area.

### 11.3 Rebuilding

YW3 header information is moved into the YWB1 layout, and the expanded block is rebuilt in this order:

```text
12-byte leading information
hash table
four u16 track pointers
four 8-byte track records
16-byte descriptor table
actual data area
```

Each descriptor's three offsets are converted from YW3 data-relative positions to absolute positions in the YWB1 block. The fourth value is written as zero.

```text
work_size = len(target_raw) + descriptor_count * 84
```

The rebuilt block is compressed with the fast LZ10 encoder. The output extension is `.mtn2`.

## 12. MTNINF2 to MTNINF

### 12.1 Conversion Function

```python
convert_mtninf2(data: bytes) -> list[bytes]
```

One MTNINF2 container produces a list of individual YWB1 MTNINF files in source-entry order.

### 12.2 Parsing

1. Enumerate contiguous 24-byte `MINF` headers from the start.
2. Require their body-relative offsets to be ascending.
3. Define each body through the next offset or EOF.
4. Require every body to contain at least 68 bytes.
5. Split any remaining body tail into special descriptors, fixed values, dynamic prefix values, and a shared compressed region.

### 12.3 Supported Special Descriptors

The 16-byte descriptor is interpreted as four u32 values.

```text
payload_size
shared_record_offset
shared_payload_offset
dynamic_count
```

Supported forms are:

| Form | Conditions |
|---|---|
| Fixed | `dynamic_count=0`, `payload_size=0`, both shared offsets equal |
| Dynamic, 8 bytes | `dynamic_count=1`, `payload_size=8`, payload offset = record offset + 4 |
| Dynamic, 12 bytes | `dynamic_count=1`, `payload_size=12`, payload offset = record offset + 4 |

`dynamic_count > 1` and other payload sizes are rejected.

### 12.4 Shared Compressed Region

- At most one non-empty shared compressed region may exist in the complete container.
- A shared region is mandatory when any dynamic descriptor exists.
- The shared region is Level-5-decompressed.
- Every dynamic reference must remain within the shared region.
- A referenced dynamic string payload must contain a NUL terminator.

### 12.5 YWB1 Special Block

One 44-byte YWB1 descriptor is generated per track, followed by dynamic prefix values and track records.

```text
record_length = 0x30 + payload_size + 4 * dynamic_count
```

Output offsets are calculated from generated positions, and marker `0x00010000` is written. A fixed track contains its 12-byte base value followed by 36 zero bytes. A dynamic track contains 32 zero bytes, dynamic count, and the referenced shared record.

When a special block exists:

```text
work_size = len(special_raw) + 0x80 * track_count
```

The special block is compressed with fast LZ10. A normal entry ends after the shared `0x60`-byte region.

## 13. Character PRM

### 13.1 Conversion Function

```python
convert_character_prm(data: bytes) -> bytes
```

### 13.2 Preconditions

- Outer magic `XMPR`.
- Outer header length `0x40`.
- Internal magic `XPRM` at `0x40`.
- The block selected by `u32@0x0C` and `u32@0x10` has length `0x4C`.
- The final 16 bytes of that block are zero.

### 13.3 Transformation

Replace the final 16 bytes of the generation-specific block with:

```hex
00 00 00 00 01 01 00 00
```

The file becomes eight bytes shorter. For outer-header offset fields at `0x10`, `0x18`, `0x20`, `0x28`, `0x30`, and `0x38`, subtract eight only when the original value points at or beyond the old end of the generation-specific block.

XPVB, XPVI, and compressed vertex data remain byte-identical. The initial policy deliberately does not reproduce the vertex rounding found in some official YWB1 assets.

## 14. Character LKAT

### 14.1 Conversion Function

```python
convert_character_lkat(data: bytes) -> bytes
```

### 14.2 Validation and Transformation

- Header length is `0x28`.
- Record length is `0x1C`.
- Total file length matches the count at `u16@0x24`.
- Set `u16@0x26` to `0x3F00`.
- Preserve every other byte.

## 15. Validated Byte-Identical Formats

Shared formats are passed through a validator rather than copied blindly. Each function returns the original `bytes` after successful validation.

### 15.1 SIL

`convert_character_sil` validates:

- `XCSL` magic.
- Header length `0x20`.
- In-range offsets and sizes for two CMBC sections.
- `CMBC` magic for each section.
- First section ends exactly where the second begins.
- Second section ends at EOF.

### 15.2 ATR

`convert_character_atr` validates:

- `ATRC01\0\0` magic.
- Header length `0x0C`.
- Layout `0x01E3` has total length 40.
- Layout `0x01E4` has total length 36.

### 15.3 MTR/LUTC

`convert_character_mtr` validates:

- `MTRC00\0\0` magic.
- Header length `0x18`.
- Reserved fields are zero.
- Total length is four-byte aligned.
- Up to three LUTC offsets are contiguous from the first slot, ascending, and unique.
- Metadata is LZ10 and expands to `0xE8` bytes.
- LUTC magic is `LUTC00\0\0`.
- LUTC fixed header values are supported.
- LUTC content is Huffman4 or RLE.
- Each LUTC expands to `0x800` bytes.

### 15.4 MBN

`convert_character_mbn` validates:

- Total length `0xA8`.
- Nonzero node-ID CRC32.
- Confirmed flag value 4 or 12.
- All 39 floats are finite.

Parent hierarchy and RES references are validated during complete p00 conversion.

### 15.5 XI

`convert_character_xi` validates:

- `IMGC00\0\0` magic.
- Confirmed header values.
- Image format `0x1B`, ETC1.
- Positive width and height, each divisible by eight.
- Tile-table and image-region sizes, placement, and zero padding.
- Huffman4 tile table.
- Expanded tile-table length `width * height / 32`.
- LZ10 image data.
- Nonempty expanded image data in 32-byte units and no larger than the ETC1 maximum.

### 15.6 TXP

`convert_character_txp` validates:

- Total length `0x24`.
- Nonzero projection-name and material-name CRC32 values.
- Seven finite floats.

The p00 set converter verifies that the referenced names exist in the RES string table.

### 15.7 CMN

`convert_character_cmn` accepts only these known types.

| Value type | Structure |
|---:|---|
| `0` | 12-byte float scalar |
| `1` | 12-byte u32/ID scalar |
| `5` | `12 + count * 8` byte array |

Array element type must be 0 (float) or 2 (CRC reference). Floats must be finite and CRC values nonzero. The p00 set converter cross-checks name CRC and variable-length metadata against RES.

## 16. RES.bin

### 16.1 Data Model

`parse_res` converts uncompressed `CHRC00/01/02` into:

```text
ParsedRes
 ├─ unknown0
 ├─ unknown1
 ├─ strings
 ├─ material_sections
 └─ node_sections
```

Each section is represented as:

```text
ResSection
 ├─ type_id
 ├─ stride
 └─ records
```

### 16.2 Parser Validation

- CHRC magic is `CHRC00`, `CHRC01`, or `CHRC02`.
- String-table offset lies within the file.
- Every string is NUL-terminated.
- Bytes after the string-table terminator are zero.
- Material and node tables lie within the file.
- Sentinel `0x270F` has count zero and stride zero.
- Every normal section has nonzero stride.
- Every record lies within RES.

### 16.3 `convert_character_res`

Only `CHRC02` is accepted as conversion input. Output version is 0 or 1.

| YW3 type | YWB1 type | Generated content |
|---:|---:|---|
| `0x012D` | `0x012C` | One eight-byte record containing CRC32(`out_00`) and zero |
| `0x0191` | `0x0190` | One eight-byte CRC32-and-zero record for each logical MTNINF2 name |

If type `0x0191` exists, the matching p80/p84 MTNINF2 is required. Logical names missing from the existing RES string table are appended.

Untouched sections, `unknown0`, `unknown1`, and existing strings are preserved. All section tables and payload locations are rebuilt in four-byte units.

### 16.4 CHRC00 and CHRC01

`res_version=1` is the default. Version 0 is available explicitly. In the current rebuilt structure, the only difference is the six-byte version magic.

```text
CHRC01  <- default
CHRC00  <- explicit selection
```

## 17. Complete p00 Internal-File Conversion

### 17.1 Core Function

```python
convert_p00_internal_files(
    files: dict[str, bytes],
    res_version: int = 1,
) -> dict[str, bytes]
```

### 17.2 File-Set Validation

- Exactly one `RES.bin`.
- No unsupported extension.
- Every extension uses an unbroken `000.ext`, `001.ext`, and so on sequence.
- At least one ATR, CMN, MBN, MTR, and PRM.
- Exactly one LKAT, SIL, and XI.
- Zero or one TXP.
- Source RES is `CHRC02`.

### 17.3 RES Count Cross-Checks

| Internal format | RES table | Type | Stride |
|---|---|---:|---:|
| ATR | Material | `0x00DC` | 8 |
| MTR | Material | `0x00E6` | 8 |
| XI | Material | `0x00F0` | 20 |
| PRM | Node | `0x0064` | 8 |
| MBN | Node | `0x006E` | 8 |
| SIL | Node | `0x0078` | 8 |
| TXP | Node | `0x008C` | 8 |
| CMN | Node | `0x00C8` | 8 |
| LKAT | Node | `0x01CC` | 8 |

If an optional format has zero files, its section must be absent. Otherwise there must be exactly one corresponding section with matching count and stride.

### 17.4 Cross-File Reference Validation

#### MBN

- RES record CRC matches the MBN node ID.
- RES reserved value is zero.
- Node IDs are unique.
- There is exactly one root, and it is `000.mbn`.
- Every non-root parent ID exists in an earlier MBN.

#### TXP

- RES record CRC matches the projection-name CRC.
- RES reserved value is zero.
- Projection-name and material-name CRC values exist in the RES string table.

#### CMN

- RES record CRC matches the parameter-name CRC.
- Parameter-name CRC exists in the RES string table.
- For variable-length CMN, RES total and extra sizes match the file length.
- Every element-type-2 CRC reference exists in the RES string table.

### 17.5 Processing Order

1. Validate filenames and the complete set.
2. Parse RES.
3. Convert or validate every internal file.
4. Cross-check MBN, TXP, and CMN against RES.
5. Convert RES to CHRC00/01.
6. Require output names to match the input set except for the rebuilt RES object.

## 18. Complete p80/p84 Internal-File Conversion

### 18.1 Core Function

```python
convert_p8_internal_files(
    files: dict[str, bytes],
    res_version: int = 1,
) -> dict[str, bytes]
```

### 18.2 Input Conditions

- Exactly one `.mtn3`.
- Exactly one `.mtninf2`.
- Exactly one `RES.bin`.
- Every other file is `.cmn`.
- Every name is a safe direct-child filename.

### 18.3 Output

- One `.mtn2` using the MTN3 stem.
- Sequential `000.mtninf` files for every MTNINF2 entry.
- Same-named validated CMN files.
- `RES.bin` rebuilt as `CHRC00` or `CHRC01`.

An output-name collision is an error.

### 18.4 Processing Order

1. Convert MTN3 to MTN2.
2. Convert MTNINF2 into individual MTNINF files.
3. Validate and preserve CMN.
4. Convert RES using the original MTNINF2.

RES `0x0190` records use logical names inside MTNINF2, not the numeric filenames assigned after splitting.

## 19. Extracted Directory Conversion

### 19.1 p00

```python
build_p00_content_outputs(source_dir, res_version)
convert_p00_content_directory(source_dir, output_dir, overwrite, res_version)
```

Only regular direct-child files are read. A subdirectory causes rejection. `build_...` returns the in-memory output dictionary; `convert_..._directory` stages and writes it.

### 19.2 p80/p84

```python
build_p8_content_outputs(source_dir, res_version)
convert_p8_content_directory(source_dir, output_dir, overwrite, res_version)
```

The same flat-directory rule applies. The input directory itself cannot be the output directory.

## 20. Raw-XC Automatic Conversion

### 20.1 p00

```python
convert_p00_xc_archive(archive, res_version) -> bytes
convert_p00_xc_file(input_path, output_dir, res_version, overwrite) -> Path
```

```text
YW3 p00 XC
 -> extract XPCK
 -> convert and cross-check p00 internal files
 -> repack XPCK and verify by re-extraction
 -> write under the original filename
```

The input filename must identify slot `p00`.

### 20.2 p80/p84

```python
convert_p8_xc_archive(archive, res_version) -> bytes
convert_p8_xc_file(input_path, output_dir, res_version, overwrite) -> Path
```

```text
YW3 p80/p84 XC
 -> extract XPCK
 -> convert MTN3, MTNINF2, CMN, and RES
 -> repack XPCK and verify by re-extraction
 -> write under the original filename
```

The filename must identify `p80` or `p84`.

### 20.3 Intermediate Files

Raw-XC conversion runs in memory and does not create a user-visible `_content` directory. Temporary files or hidden staging directories are used only during final writes and are removed afterward.

## 21. Three-Archive Character Conversion

### 21.1 Discovery

`find_character_xc_files` accepts either:

- A directory containing one character's three XC archives.
- Any one member of the three-file set.

For directory input, every XC must belong to one case-insensitive base name. For file input, only sibling XC archives with the selected file's base name are considered.

### 21.2 Consistency Checks

- Exactly one p00, p80, and p84.
- No duplicate slot.
- One case-insensitive base name shared by all three.
- A nonstandard XC name is not silently ignored during directory discovery.

### 21.3 Conversion

```python
convert_character_xc_archives(archives, res_version) -> dict[str, bytes]
convert_character_xc_set(input_path, output_dir, res_version, overwrite) -> list[Path]
```

p00 is dispatched to the p00 pipeline; p80 and p84 use the p8 pipeline. All three conversions and XPCK self-checks complete before files are staged for output. Input filenames are preserved.

## 22. File Writing and Overwrite Policy

### 22.1 Default

An existing same-named output is an error. Source files and source directories are never rewritten directly.

### 22.2 `--overwrite`

Only explicit use of `--overwrite` allows same-named output replacement. Unrelated files in the output directory remain untouched.

### 22.3 Single File

`write_single_output` creates a temporary file in the destination directory and calls `os.replace` only after the write completes. A partially written final file is therefore not exposed during normal failure handling.

### 22.4 Multiple Files

`write_named_outputs` and `write_outputs` first write every result into a temporary staging directory. No final destination is modified until conversion and staging have succeeded.

When the destination directory already exists, target files are replaced one by one with `os.replace`. Complete transactionality across multiple files is therefore not guaranteed if an OS-level failure occurs midway, although normal format errors are found before replacement begins.

### 22.5 In-Place Output Restrictions

- Single-file conversion rejects the input file itself as output.
- XC conversion rejects a destination that would be the same path and filename as the source XC.
- `pack-xc` rejects an output XC inside the input internal-file directory.
- Extracted-content conversion rejects the input directory itself as output.

## 23. CLI Specification

General syntax:

```text
python character_converter.py <command> [arguments] [options]
```

### 23.1 Commands

| Command | Input | Output | Purpose |
|---|---|---|---|
| `character-xc` | Directory containing three XC files, or any one member | Directory | Recommended complete p00/p80/p84 conversion |
| `p00-xc` | Raw p00 XC | Directory | Convert p00 only |
| `p8-xc` | Raw p80 or p84 XC | Directory | Convert one p80/p84 archive |
| `p00-content` | Extracted p00 directory | Directory | Convert complete internal-file set |
| `p8-content` | Extracted p80/p84 directory | Directory | Convert complete internal-file set |
| `pack-xc` | Converted internal-file directory | XC file | Repack XPCK |
| `mtn3` | `.mtn3` | `.mtn2` | Single-file conversion |
| `mtninf2` | `.mtninf2` | Directory | Split into individual MTNINF files |
| `prm` | `.prm` | `.prm` | Single-file conversion |
| `lkat` | `.lkat` | `.lkat` | Single-file conversion |
| `sil` | `.sil` | `.sil` | Validated byte-identical copy |
| `res` | `RES.bin` | `RES.bin` | Single-file conversion |

ATR, MTR, MBN, XI, TXP, and CMN do not have standalone CLI commands. They are handled through `p00-content`, `p00-xc`, or `character-xc`, where cross-file validation is available.

### 23.2 Shared Options

| Option | Commands | Meaning |
|---|---|---|
| `--overwrite` | Every command that writes output | Replace existing same-named output |
| `--res-version 0` | Operations containing RES | Write `CHRC00` |
| `--res-version 1` | Operations containing RES | Write `CHRC01`; default |

### 23.3 Context for Single RES

The `res` command accepts `--context-dir`. If omitted, it searches the parent of the input RES for at most one `.mtninf2`.

- p00 RES does not require MTNINF2.
- p80/p84 type `0x0191` conversion requires matching MTNINF2.
- Multiple MTNINF2 files are ambiguous and rejected.

## 24. Public Function Responsibilities

### 24.1 Compression and Containers

| Function | Responsibility |
|---|---|
| `level5_decompress` | Decode kinds 1, 2, 3, and 4 |
| `level5_lz10_compress` | LZ10 for large rebuilt blocks |
| `level5_lz10_compress_canonical` | LZ10 for XPCK name table and RES |
| `unpack_xpck_archive` | Validate and extract XPCK |
| `pack_xpck_files` | Build and self-check XPCK |
| `pack_xpck_directory` | Build XPCK from a flat directory |

### 24.2 Individual Formats

| Function | Responsibility |
|---|---|
| `convert_mtn3` | MTN3 to MTN2 |
| `convert_mtninf2` | MTNINF2 to multiple MTNINF files |
| `convert_character_prm` | Character PRM generation downgrade |
| `convert_character_lkat` | LKAT compatibility conversion |
| `convert_character_sil` | Validate and preserve SIL |
| `convert_character_atr` | Validate and preserve ATR |
| `convert_character_mtr` | Validate and preserve MTR/LUTC |
| `convert_character_mbn` | Validate and preserve MBN |
| `convert_character_xi` | Validate and preserve XI |
| `convert_character_txp` | Validate and preserve TXP |
| `convert_character_cmn` | Validate and preserve CMN |
| `convert_character_res` | CHRC02 RES to CHRC00/01 |

### 24.3 Sets and XC Archives

| Function | Responsibility |
|---|---|
| `convert_p00_internal_files` | Convert p00 set and validate cross-references |
| `convert_p8_internal_files` | Convert p80/p84 set |
| `convert_p00_xc_archive` | Complete in-memory p00 XPCK conversion |
| `convert_p8_xc_archive` | Complete in-memory p80/p84 XPCK conversion |
| `character_archive_slot` | Determine slot from XC filename |
| `find_character_xc_files` | Discover one character's three files |
| `convert_character_xc_archives` | Convert three archives in memory |
| `convert_character_xc_set` | Discover, convert, and write a three-file set |

## 25. Test Specification

Tests live in `character_convert/test_*.py` and consist of 10 modules and 43 test methods.

| Test module | Main coverage |
|---|---|
| `test_mtn3_converter.py` | 20 MTN3 pairs, compression kinds, rejection of unknown descriptor values |
| `test_mtninf2_converter.py` | 244 entries, normal/fixed/dynamic/carrier forms, overwrite behavior |
| `test_prm_converter.py` | 24 YW3 PRMs, 23 official pairs, preserved regions, error cases |
| `test_lkat_sil_converter.py` | 10 LKAT and 10 SIL files, malformed structures |
| `test_res_converter.py` | 30 RES files, CHRC00/01, required context |
| `test_p8_content_converter.py` | 20 extracted p80/p84 conversions |
| `test_p8_xc_converter.py` | 20 raw p80/p84 archives, automatic conversion, slot validation |
| `test_p00_converter.py` | 10 p00 content sets, 10 raw p00 archives, broken-reference rejection |
| `test_xpck_converter.py` | 60 official XPCK extractions, 20 exact official p8 repacks |
| `test_character_xc_set_converter.py` | 10 character trios, discovery, overwrite, mixed-set rejection |

### 25.1 Comparison Criteria

Tests distinguish between:

- Generation structures that must exactly match official YWB1 output.
- Structures whose decompressed form must match even when compression differs.
- Official YWB1 content revisions that must not replace the original YW3 asset values.
- Unknown structures and broken references that must be rejected.

### 25.2 In-Game Validation

Automatically converted `p00`, `p80`, and `p84` output has been confirmed in both an emulator and on real hardware. Automated tests establish structural correctness; model appearance, animation, and collision behavior must still be checked in game.

## 26. Major Design Decisions

### 26.1 Do Not Import the Effect Converter

XPCK and Level-5 knowledge is shared, but the character implementation does not import the effect converter so the two tools can evolve independently.

This does not imply that duplication must remain forever. A future shared library should extract only side-effect-free compression and XPCK code while preserving both converters' regression suites.

### 26.2 Do Not Replace Content Differences as Though They Were Format Differences

Official YWB1 pairs include vertex rounding, node additions/removals, LUT changes, texture changes, animation revisions, and bounding-value adjustments. Shared-format YW3 content is preserved rather than overwritten with unrelated YWB1 asset revisions.

### 26.3 Validated Copy

“Usable unchanged” does not mean “accept arbitrary input.” Only known layouts pass. A future unknown form is returned to analysis instead of silently copied.

### 26.4 Do Not Re-Round PRM

The initial implementation preserves XPVB/XPVI and modifies only the generation-specific compatibility block. It avoids model-content changes not required for runtime compatibility.

### 26.5 Normalize MTN Output to LZ10

YW3 input contains both LZ10 and Huffman8. The logical block is rebuilt for YWB1 and output is consistently encoded as LZ10 for implementation simplicity and validation. A differing compression kind does not make the output invalid.

### 26.6 Convert Raw XC in Memory

Avoiding a user-managed intermediate directory prevents mixing stale extracted files, using the wrong content set, or forgetting to repack. Internal-file commands remain available for research and diagnosis.

### 26.7 Validate Three-File Names Before Conversion

XC archives from different characters can each be individually valid. Three-file conversion therefore verifies the shared character base name before processing.

### 26.8 Preserve Output Names

Keeping the original XC filenames eliminates a manual renaming step before ROM replacement. Safety is provided by using a separate output directory.

### 26.9 Default to CHRC01

The initial standard output is `CHRC01`; `CHRC00` remains selectable. Both versions use the same rebuild logic and differ only in the selected magic under the current rules.

## 27. Safety and Robustness

### 27.1 Path Traversal

XPCK filenames cannot contain directory separators, `.`, `..`, or a drive separator. Repacking accepts only direct-child names.

### 27.2 Integer Ranges

Values are checked before storage in XPCK, RES, or MTN 16-bit and 24-bit fields. Python integers are never silently truncated.

### 27.3 Compressed Data

Decoders validate source termination, reference distance, tree references, and output length. A malformed stream cannot read indefinitely beyond input.

### 27.4 Floating-Point Values

MBN, TXP, and CMN reject NaN and infinity. Semantic value ranges are not guessed.

## 28. Known Limitations

- Supported layouts are based on the analyzed corpus.
- New ATR layout IDs, MBN flags, XI formats, and CMN types are rejected.
- Only zero is supported for the fourth MTN3 descriptor value.
- MTNINF2 dynamic count is limited to zero or one.
- XPCK is a flat file collection.
- Filename CRC32 collisions are rejected rather than renamed.
- p80/p84 content is limited to MTN3, MTNINF2, CMN, and RES.
- Some p00 field meanings remain unknown, but known structure is validated strictly enough to perform the compatibility conversion safely.

## 29. Adding a New Format Variant

When an unknown form is found, do not weaken validation before completing these steps:

1. Add the YW3 input and, if possible, its corresponding YWB1 file.
2. Compare compressed and expanded data, RES references, counts, and file ordering.
3. Classify the difference as a generation structure or an asset-content revision.
4. Add a new branch to the pure bytes-layer function.
5. Keep regression tests proving the behavior of existing forms.
6. Validate new cross-references against RES in set conversion.
7. Repack XPCK and verify re-extraction equality.
8. Test in an emulator and finally on real hardware.
9. Update the format analysis, implementation specification, and user guide.

## 30. Completion Criteria

A character conversion is complete only when all of the following are true:

- The p00, p80, and p84 base names match.
- All three XC archives extract successfully.
- Every internal file passes its known structural validation.
- Required generation transformations succeed.
- RES counts and CRC references agree with internal files.
- No YW3-generation extension remains.
- All three archives repack successfully as XPCK.
- Re-extracting each archive exactly reproduces its converted internal-file set.
- All three archives are written under their input filenames in the requested output directory.
- Final in-game testing confirms the model and relevant animations work correctly.
