# YW3 to YWB1 Character XC Converter Implementation Specification

## 1. Purpose of This Document

This document specifies the external behavior, internal design, conversion pipelines, validation rules, input/output policy, error handling, and test strategy of `character_converter.py`, which converts Yo-kai Watch 3 (YW3) character XC archives for use in Yo-kai Watch Blasters (YWB1).

For the evidence behind the binary rules, sample counts, field interpretations, and the distinction between confirmed and unknown details, see the format-analysis document:

- [FORMAT_ANALYSIS.md](./FORMAT_ANALYSIS.md)

This specification records how those findings are implemented. End-user commands and workflows are documented separately:

- [USER_GUIDE.md](./USER_GUIDE.md)

The implementation is contained in:

```text
character_converter.py
```

That script is at the root of the cloned or extracted public repository and uses only Python's standard library. The public release contains seven files: the script, `README.md`, `USER_GUIDE.md`, `FORMAT_ANALYSIS.md`, this specification, `LICENSE.md`, and `.gitignore`. No ROM/XC samples, extracted-content directories, tests, development tools, or audit JSON files are distributed. Test/tool names and corpus counts in this specification document the private development evidence; they are not missing release dependencies or commands you can run against bundled fixtures. Prepare your own inputs as described in the user guide.

## 2. Scope

Full-corpus recovery on 2026-10-14 supersedes the initial ten-sample-only limits. That strict-conversion audit structurally converted 2,843 of 2,949 supplied p00/p80/p84 XC files, leaving 106 unresolved: 104 p00 internal-conversion cases and two special motion cases. This remains historical evidence for the strict path, not a claim that 104 unchanged models are impossible to transplant. New archive-level regression tests are `test_character_archive_recovery.py`, `test_character_model_recovery.py`, `test_character_motion_recovery.py`, and `test_character_xi_recovery.py` (39 tests at that audit). Corpus-dependent cases use private ROM inputs and skip when absent; historical tests referring to the removed original extracted fixtures are not represented as newly passing tests.

The corpus-wide audit processes every existing target XC independently, including characters missing one or more of the three slots. Default `character-xc` still requires a complete trio and strict conversion of every member. The explicit `--copy-p00` mode added on 2026-10-15 permits partial major-slot sets and copies a present p00 unchanged; [Appendix C](#appendix-c-explicit-p00-copy-and-auto-cli) defines its reduced validation guarantee. No conversion of other XC slots or XV/XR is implied. No new variant is claimed game-tested.

### 2.1 Supported XC Slots

The converter handles three principal archive slots per character. A complete trio is required by default; explicit p00-copy mode can process an available subset.

| Slot | Contents | Main operation |
|---|---|---|
| `p00` | Model-related resources | Convert PRM, LKAT, and RES; validate and preserve the remaining model formats |
| `p80` | Motion-related resources | Convert supported MTN/MTM/IMM and INF families, rebuild RES, and process optional CMN/LKAT/SIL |
| `p84` | Motion-related resources | Convert supported MTN/MTM/IMM and INF families, rebuild RES, and process optional CMN/LKAT/SIL |

This table describes strict conversion. Explicit `--copy-p00` replaces the p00 operation with XPCK container validation and original-byte preservation; the present p80/p84 operations remain unchanged.

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

The motion/RES rows below describe the initial ten-pair implementation. [Appendix M](#appendix-m-full-corpus-motion-update) supersedes the initial-only restrictions with the current full-corpus motion and RES behavior.

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
| `xi` | Preserve after IMGC00 and verified-image-format validation |
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

The internal-format transformation/validation and repack requirements describe strict conversion. Explicit p00 preservation in Appendix C replaces them for that one slot with container validation and whole-archive byte identity; motion conversion remains strict.

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
| `sys` | Read command-line arguments for `--auto` normalization |
| `tempfile` | Temporary files and directories |
| `dataclasses` | Parsed binary structures |
| `pathlib` | Path handling |
| `typing` | Type annotations such as `Sequence` |

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

The strict conversion paths do not zero unknown fields, round them to a nearby known value, or silently drop unsupported files. They stop as soon as input falls outside the analyzed structures. Explicit p00-copy mode is not a guessed transformation: it checks the container and retains the entire source archive without validating or converting its model internals. Motion paths remain strict in either mode.

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

The initial table below predates kind-0 source blocks. The current decoder accepts kinds 0–4; see [Appendix M](#appendix-m-full-corpus-motion-update).

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

This single-output API remains compatible. The archive pipeline uses the multi-entry family API in [Appendix M](#appendix-m-full-corpus-motion-update) for bundled MTN/MTM/IMM.

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

The table below is the initial supported set. A=4/event `0x05E4` is now supported only under its separately verified rule; A=4/event `0x044E` and A=16 remain unsupported. See [Appendix M](#appendix-m-full-corpus-motion-update).

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

Already-old PRMs with a `0x44` block are also accepted as byte-identical copies after validating the known eight-byte marker and name/material-name ranges. An unknown nonzero tail in a `0x4C` source block is not treated as safely removable padding.

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

This is the retained normalization policy confirmed for the initial pairs and prior game-tested samples, not a proven semantic version field. The B1-only `y275010` packed-header exception is unparsed; no supplied YW3 LKAT has that form. See the LKAT caveat in the format-analysis document.

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
- The block at `0x0C` is Level-5 compressed data, not a layout identifier.
- `0x01E3` and `0x01E4` encode 60 decoded bytes with compression kind 3 or 4.
- The decoded payload is exactly 60 bytes and starts with the value 60. Compressed length is variable.

### 15.3 MTR/LUTC

`convert_character_mtr` validates:

- `MTRC00\0\0` magic.
- Header length `0x18`.
- Reserved fields are zero.
- Total length is four-byte aligned.
- Up to three independent LUTC slots may be zero. Nonzero offsets remain ascending, unique, aligned, and in range; a zero slot between populated slots is valid.
- Metadata is LZ10 and expands to `0xE8` bytes.
- LUTC magic is `LUTC00\0\0`.
- LUTC fixed header values are supported.
- LUTC content is Huffman4 or RLE.
- Each LUTC expands to `0x800` bytes.

### 15.4 MBN

`convert_character_mbn` validates:

- Total length `0xA8`.
- Nonzero node-ID CRC32.
- Confirmed flag value 4, 5, or 12.
- All 39 floats are finite.

Parent hierarchy and RES references are validated during complete p00 conversion.

### 15.5 XI

`convert_character_xi` validates:

- `IMGC00\0\0` magic.
- Confirmed header values.
- Image formats `0x1B` (32 bytes per stored 8-by-8 tile) and `0x1C` (64 bytes per tile), with their observed associated header fields.
- Positive width and height, each divisible by eight.
- Tile-table and image-region sizes, placement, and zero padding.
- Tile-table aligned size at `0x38` equals `align4(u32@0x34)`, not necessarily the unaligned size.
- Supported Level-5 compression kinds 0 through 4 for both tile and image data.
- Expanded tile-table length `width * height / 32`.
- Nonempty expanded image data in the format's tile-byte units, bounded by the image dimensions.
- The decoded u16 tile indices cover exactly `0..stored_tile_count-1`; malformed or missing references are rejected.
- Format `0x04` has no B1 example in the supplied corpus and remains unsupported.

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

The single-root MTN rule below is the legacy positional-API behavior. Full archive conversion now supplies category-aware context and actual animation identities as specified in [Appendix M](#appendix-m-full-corpus-motion-update).

In the initial implementation, only `CHRC02` was accepted as conversion input. The current implementation also checks and reserializes known `CHRC00/01` inputs, as specified in Appendix M. Output version remains 0 or 1.

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
- At least one CMN and MBN. Bone-less p00 models remain unsupported because no B1 example establishes their loading rule.
- Other known model kinds may be absent or repeated; their file counts must exactly match the corresponding RES sections.
- Multiple XI, TXP, and LKAT files are supported. Missing material resources are valid for bone/parameter-only models when their RES sections are also absent.
- Source RES may be `CHRC02`, or an already-old `CHRC00/01` resource with validated references.
- Unknown model RES type `0x0123` and `prmgrp` remain rejected.

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
- Element-type-2 CRC references may resolve outside the local RES string table; native B1 MESH_DRAW_ALP0 and SHADOW records establish this. Their type and nonzero value are validated, but external game-context resolution is not claimed.
- Array element type 1 is still unsupported. The unique `COLLISION_RECT` scalar with RES size metadata `(12,0)` also remains rejected rather than being silently normalized to `(0,0)`.

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

These are the initial-corpus conditions, not current universal limits. Bundles, optional IMM/MTM, old resources, and optional LKAT/SIL follow [Appendix M](#appendix-m-full-corpus-motion-update).

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

For directory input, every selected major XC must belong to one case-insensitive base name. Non-major XC slots are ignored in both normal and copy modes. For file input, the file must identify p00/p80/p84; only major sibling XC archives with its base name are considered. Discovery is not recursive.

### 21.2 Consistency Checks

- Exactly one p00, p80, and p84 in default strict mode; one to three available major slots in explicit copy mode.
- No duplicate slot.
- One case-insensitive base name shared by all selected files.
- Directory discovery ignores XC filenames that do not identify a major slot; those files are neither converted nor copied.

### 21.3 Conversion

```python
convert_character_xc_archives(archives, res_version=1, *, copy_p00=False) -> dict[str, bytes]
convert_character_xc_set(input_path, output_dir, res_version=1, overwrite=False, *, copy_p00=False) -> list[Path]
```

By default, p00 is dispatched to the p00 pipeline and p80/p84 use the p8 pipeline. With `copy_p00=True`, a present p00 is container-validated and its original XC bytes are returned without internal conversion or repacking; present motion slots still use the normal p8 pipeline. All selected files are prepared and checked before output staging begins. Missing slots are permitted only in copy mode and are never synthesized. Input filenames are preserved.

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

Equivalent automatic shorthand:

```text
python character_converter.py INPUT OUTPUT_DIRECTORY --auto [--copy-p00]
```

`--auto` selects `character-xc`; it is not recursive corpus conversion. See [Appendix C](#appendix-c-explicit-p00-copy-and-auto-cli).

### 23.1 Commands

| Command | Input | Output | Purpose |
|---|---|---|---|
| `character-xc` | One-character major-XC directory, or any one major member | Directory | Strict complete-trio conversion by default; explicit copy mode permits a partial set |
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
| `--res-version 0` | Operations converting RES | Write `CHRC00`; copied p00 is unaffected |
| `--res-version 1` | Operations converting RES | Write `CHRC01`; default; copied p00 is unaffected |
| `--copy-p00` | `character-xc` / `--auto` shorthand | Container-validate and preserve present p00; allow missing major slots; normally convert present p80/p84 |
| `--auto` | Automatic shorthand; redundant with explicit `character-xc` | Dispatch the input/output form to the character-set operation |

### 23.3 Context for Single RES

The `res` command accepts `--context-dir`. If omitted, it searches the parent of the input RES for at most one `.mtninf2`.

- p00 RES does not require MTNINF2.
- p80/p84 type `0x0191` conversion requires matching MTNINF2.
- Multiple MTNINF2 files are ambiguous and rejected.

## 24. Public Function Responsibilities

### 24.1 Compression and Containers

| Function | Responsibility |
|---|---|
| `level5_decompress` | Decode kinds 0, 1, 2, 3, and 4 |
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
| `convert_character_res` | Rebuild known CHRC00/01/02 RES as the selected CHRC00/01, using supplied reference context |

### 24.3 Sets and XC Archives

| Function | Responsibility |
|---|---|
| `convert_p00_internal_files` | Convert p00 set and validate cross-references |
| `convert_p8_internal_files` | Convert p80/p84 set |
| `convert_p00_xc_archive` | Complete in-memory p00 XPCK conversion |
| `convert_p8_xc_archive` | Complete in-memory p80/p84 XPCK conversion |
| `character_archive_slot` | Determine slot from XC filename |
| `find_character_xc_files` | Discover one character's major files; complete trio by default, partial when explicitly allowed |
| `convert_character_xc_archives` | Prepare a same-character major-XC set in memory; strict trio or explicit p00-copy subset |
| `convert_character_xc_set` | Discover, prepare, and write the selected major-XC set |

## 25. Test Specification

The test modules below belong to the private development workspace and are **not included in this public release**. The original extracted-fixture suite consisted of 10 modules and 43 methods; it is retained here as historical coverage. Current recovery and explicit-copy suites are described in Appendices M and C. Missing private extracted fixtures are not represented as passing historical tests. These module names describe verification evidence, not files or game samples shipped with a minimal checkout.

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

The original automatically converted sample `p00`, `p80`, and `p84` sets were confirmed by the user in both an emulator and on real hardware. Later full-corpus variants and explicit-copy checks have structural or byte-preservation verification, not new all-corpus game confirmation. Automated tests establish implementation contracts; model appearance, animation, and collision behavior must still be checked in game.

## 26. Major Design Decisions

### 26.1 Do Not Import the Effect Converter

XPCK and Level-5 knowledge is shared, but the character implementation does not import the effect converter so the two tools can evolve independently.

This does not imply that duplication must remain forever. A future shared library should extract only side-effect-free compression and XPCK code while preserving both converters' regression suites.

### 26.2 Do Not Replace Content Differences as Though They Were Format Differences

Official YWB1 pairs include vertex rounding, node additions/removals, LUT changes, texture changes, animation revisions, and bounding-value adjustments. Shared-format YW3 content is preserved rather than overwritten with unrelated YWB1 asset revisions.

### 26.3 Validated Copy

“Usable unchanged” does not mean “accept arbitrary input.” Only known layouts pass. A future unknown form is returned to analysis instead of silently copied.

This statement applies to the per-format validators and strict internal conversion. Explicit whole-p00 preservation is a separate container-only policy described in Appendix C; it does not declare unknown model layouts supported by those validators.

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

The historical motion-file restriction below is superseded by [Appendix M](#appendix-m-full-corpus-motion-update). Unknown special types remain rejected; newly supported families do not imply arbitrary unknown-file copying.

- Supported layouts are based on the analyzed corpus.
- ATR is validated by decoded structure, not compressed file length. MBN flags outside 4/5/12, XI formats outside 0x1B/0x1C, and unverified CMN types are rejected.
- Only zero is supported for the fourth MTN3 descriptor value.
- MTNINF2 dynamic count is limited to zero or one.
- XPCK is a flat file collection.
- Filename CRC32 collisions are rejected rather than renamed.
- p80/p84 additionally supports bundled MTM3/IMM3, their normal INF2 bundles, verified existing v2 animations/INF, and validated LKAT/SIL. See the full-corpus motion appendix for exact limits.
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

A default strict three-archive conversion is complete only when all of the following are true. Explicit copy-mode completion follows [Appendix C](#appendix-c-explicit-p00-copy-and-auto-cli) instead and is not a claim that p00 internals were converted:

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

## Appendix M: Full-Corpus Motion Update

### M.1 Precedence and verification status

**Full-corpus recovery supersedes the initial-only restrictions** on compression, motion families, bundle cardinality, and RES root construction in the main specification. Original sample counts and game-test results remain historical evidence. This appendix describes the implemented bytes-layer and archive-path behavior, not a claim that every new full-corpus output has been tested in game.

Only p00/p80/p84 XC slots are in the requested full-corpus scope. Testing an existing p80 or p84 does not require its character to have the other two XCs. The independent `p8-xc` path and the corpus audit can process each present motion archive. Default character-set conversion remains a complete-trio operation. Explicit p00-copy mode now accepts available major slots as specified in [Appendix C](#appendix-c-explicit-p00-copy-and-auto-cli); it does not synthesize missing archives.

Binary layout evidence and the detailed source/target tables are in [FORMAT_ANALYSIS.md, Appendix M](FORMAT_ANALYSIS.md#appendix-m-full-corpus-motion-update).

### M.2 Shared decompression update

`level5_decompress` accepts Level-5 kinds 0, 1, 2, 3, and 4. Kind 0 has the usual four-byte size/kind word, followed directly by the payload:

```python
kind = header & 7
output_size = header >> 3
require(output_size <= len(data) - 4, ...)
decoded = data[4:4 + output_size]
```

It does not return trailing padding. Truncation remains an error, including a kind-0 block that advertises more bytes than are present. Unknown kinds remain errors. This change does not alter the LZ10/Huffman/RLE decoding algorithms or force shared-format copied files to change their compression.

Generation-2 rebuilt animation blocks and special MINF blocks use the existing fast LZ10 encoder. XPCK filename tables and RES use the existing canonical LZ10 encoder. Logical equality, rather than compressed-byte identity, remains the comparison standard.

### M.3 New motion bytes-layer functions

| Function | Contract |
|---|---|
| `split_character_animation3(data, extension)` | Validate the source family's consecutive headers/body ranges/shared block and return conventional single-entry source payloads. |
| `convert_character_animation3(data, extension)` | Return `list[bytes]`, one generation-2 payload for every logical MTN3/MTM3/IMM3 entry. |
| `convert_mtn3_entries(data)` | MTN-specific list-returning wrapper around the family conversion function. |
| `convert_simple_inf2(data, extension)` | Return ordinary MTMINF/IMMINF files only for exactly 68-byte source bodies and zero special-track counts. |
| `validate_character_animation2(data, extension, *, allow_name_alias=False)` | Validate known MTN2/MTM2/IMM2 structures and return the original bytes. |
| `validate_character_inf(data, extension)` | Validate known MTNINF/MTMINF/IMMINF structures, bounded logical-name CRC, and special regions, then return original bytes. |

The supported generation-3 extensions are `.mtn3`, `.mtm3`, and `.imm3`. The target extensions are `.mtn2`, `.mtm2`, and `.imm2`, respectively. MTM/IMM support is integrated into `p8-content`, `p8-xc`, and automatic character conversion; no new standalone CLI command named `mtm3`, `imm3`, `mtminf2`, or `imminf2` is implied by adding these internal functions.

`convert_mtn3(data) -> bytes` and the existing `mtn3` CLI preserve their established single-output contract. A source with multiple logical MTN entries must use the archive path or the list-returning API; one output path is not sufficient for that bundle.

### M.4 Source splitting and target invariants

The layout table fixes each family's magic, header size, track-category count, descriptor-count fields, used-length field, decoded-entry-base field, and target outer offsets. These are format parameters, not values inferred from a matching B1 character during conversion.

Source splitting requires:

1. At least one complete consecutive header with the correct family magic.
2. Name/body regions contiguous in logical-header order.
3. Pointer start exactly 48 bytes after that entry's name start; descriptor start exactly another `2 * track_count` bytes later.
4. `u32@0x08` equal to `4 * hash_count + 8 * track_count`.
5. All source descriptor tables in bounds before the shared compressed region.
6. Ordered, nonoverlapping decoded-entry ranges containing their prefix and advertised used bytes.
7. Zero-filled unclaimed decoded gaps and trailing padding in the bundled-splitting path.

A verified single-entry source can reuse its original block instead of needlessly recompressing an intermediate source. The established ordinary single-MTN conversion path is retained for binary-output compatibility.

For each logical entry, the target table positions are rebuilt from `H`, `T`, and `D`:

```text
pointer_start    = 12 + 4H
record_start     = pointer_start + 2T
descriptor_start = record_start + 8T
data_start       = descriptor_start + 16D
```

Source hashes, track records, and exactly the claimed used-data bytes are preserved. The three descriptor data pointers are rebased by adding `data_start`; their fourth field must be zero. Source-relative pointers must lie inside the used-data area, and generated u16 track pointers must remain representable. The target work size is `len(target_raw) + 84D`. No unknown descriptor fields are silently cleared to recover an archive.

Target animation validation independently checks the magic, reserved outer fields, name/compressed offsets, nonzero stored name identity, bounded readable-name termination, decoded three-word table header, track pointers, descriptor ranges/fourth fields, and work-size formula. Default legacy-copy validation also requires the readable name's CRC to equal the stored identity.

### M.5 INF names, ordinary entries, and special entries

MTMINF2/IMMINF2 reuse the existing MINF2 header/body parser, but their currently supported bodies must be exactly 68 bytes and have zero special-track count. The target common prefix, copied count word, and body produce exactly 96 bytes. A special or additional payload is rejected rather than passed through or stripped.

`validate_character_inf` validates a nonempty logical name inside the **44-byte** target field `[0x20, 0x4C)`. It requires a NUL terminator within that interval and checks:

```text
u32(target, 0x1C) == CRC32(target[0x20 : first_NUL_inside_0x4C])
```

The raw byte sequence is used without a text-encoding round trip. The following root/playback fields are not searched for a terminator. This check applies equally to generated and byte-preserving copied INF files.

For an ordinary INF entry, total size must be 96 bytes and work size must be zero. Only MTNINF may currently contain special data. Its validator requires a complete 44-byte-per-track descriptor table; in-bounds records at least 48 bytes long; dynamic count 0 or 1; the expected data pointer; marker `0x00010000`; zero-reserved descriptor words; and `work_size = len(special_raw) + 128 * track_count`.

The special MTNINF2 supported set now includes the original fixed, A=8, and A=12 forms plus **A=4 with event/type `0x05E4` only**. The event code is the last u32 in the matching 12-byte fixed value. This additional form still requires `D=1`, `C=B+4`, auxiliary value 4, and valid shared-data bounds. Its verified four-byte non-string payload is not subject to the string NUL requirement. All output-position and work-size formulas are unchanged.

Two different forms remain rejected: `x611000_p80/000.mtninf2` A=4/event `0x044E` with auxiliary value 0, and `x791000_p84/000.mtninf2` A=16. Both lack an established B1 rule. No fallback strips their special information or changes them into the known event type.

### M.6 Current p80/p84 file-set contract

`convert_p8_internal_files` retains its signature and now accepts these known internal suffixes in addition to exactly one `RES.bin`:

```text
Generation-3 animation bundles: mtn3, mtm3, imm3
Generation-2 animation files:   mtn2, mtm2, imm2
Information bundles:           mtninf2, mtminf2, imminf2
Individual information files:  mtninf, mtminf, imminf
Optional shared resources:     cmn, lkat, sil
```

Every filename must remain a safe direct-child name. Numbered animation/INF filenames must be consecutive from `000` within their own extension. At most one generation-3 physical bundle is allowed per family; the same family cannot mix that source bundle and pre-existing generation-2 files. The equivalent no-mixing rule applies to INF2 bundles and individual old INF files. At least one MTN animation source (`mtn3` or `mtn2`) and MTN information source (`mtninf2` or `mtninf`) are required. Optional IMM/MTM families are processed when present rather than imposed on every character.

Processing order is:

1. Convert each generation-3 animation family into numbered generation-2 outputs, or validate and preserve existing generation-2 files.
2. Convert each supported INF2 family into numbered individual outputs, or validate and preserve individual old INF files.
3. Validate CMN and SIL; convert LKAT with its established standalone rule.
4. Rebuild RES using all generated/copied animation/INF outputs and the source INF2 bundles.
5. Repack and verify the converted file set through the existing XPCK layer.

Logical order is preserved independently for each extension. Output filename collisions are errors. Exceptions from bundle conversions identify the source internal filename. Unknown suffixes remain errors; extension recognition is not an unrestricted copy fallback.

### M.7 Expanded RES API and category reconstruction

The current bytes-layer signature is:

```python
convert_character_res(
    data: bytes,
    mtninf2_data: bytes | None = None,
    version: int = 1,
    *,
    animation_files: dict[str, bytes] | None = None,
    inf2_files: dict[str, bytes] | None = None,
) -> bytes
```

In the archive path, `animation_files` contains the converted/copied generation-2 animation and individual INF outputs; optional other converted files in that dictionary do not become animation roots. `inf2_files` contains the original `.mtninf2`, `.mtminf2`, and `.imminf2` bundles. A supplied positional `mtninf2_data` must not conflict with the bundle dictionary.

| Family | New type | Old type | Old reference identity |
|---|---:|---:|---|
| MTN | `0x012D` | `0x012C` | Stored MTN2 ID at `0x28` |
| IMM | `0x0137` | `0x0136` | Stored IMM2 ID at `0x24` |
| MTM | `0x0141` | `0x0140` | Stored MTM2 ID at `0x24` |
| MTNINF | `0x0191` | `0x0190` | Bounded logical-name CRC |
| IMMINF | `0x019B` | `0x019A` | Bounded logical-name CRC |
| MTMINF | `0x01A5` | `0x01A4` | Bounded logical-name CRC |

Every new category must have one physical 28-byte source record. That one record expands into an 8-byte `(identity, 0)` record for each logical output in the corresponding family. The count is the number of actual logical outputs, not the number of physical source files. `out_00` is not substituted for other roots in the archive path.

The converter rejects duplicate old/new category sections, wrong new strides/counts, wrong legacy strides/nonzero reserved words, and mismatched converted-file category presence, count, order, or identities. The rebuilt INF references must match the validated generated/copied individual INF names. An already-old category is checked against the current files rather than blindly trusted. Existing strings retain their order; missing logical/readable names are appended.

CHRC00/CHRC01 inputs are supported without another generation downgrade. Old internal v2/INF payloads remain byte-identical after validation; RES is parsed, checked, and reserialized with the selected version. This does not promise unconditional byte identity of old RES serialization. CHRC01 remains the default, CHRC00 remains selectable, and the serializer uses the same structure for both versions with their respective magic.

The old positional-only RES API preserves the initial MTN `out_00` compatibility behavior. The `res` CLI still searches only for a sibling/context `.mtninf2`; it is not automatically a complete source of multi-family or multi-root animation context. Use `p8-content`, `p8-xc`, or automatic character conversion for those full-archive cases, or call the expanded bytes API with both dictionaries. Merely passing one RES.bin to the old standalone command is not equivalent to converting its entire XC.

### M.8 Source aliases and the stored-ID decision

The official YW3 y699000 IMM bundles are renamed copies of y159000 bundles: reversing the readable-name substitution yields exact byte equality, including the stored identities, descriptors, and shared block. Recalculating those identities from the renamed readable strings would change the source identity and its references.

Generation conversion therefore preserves both the stored nonzero identity and readable name. Generated-v2 validation calls `validate_character_animation2(..., allow_name_alias=True)`. RES context validation permits the same source-alias condition when INF2 bundle context is supplied and writes actual stored animation IDs into the old references. Existing-v2 file copying uses the default strict name-CRC check. INF logical-name CRC validation remains strict; this option is not a blanket waiver for all names or reference errors.

This policy is an inference grounded in official renamed source resources and the shared binary placement, not a same-name B1 comparison or demonstrated B1 game success for y699000. The new alias outputs remain a priority for game testing. The stored ID is never repaired by guessing a replacement character prefix.

### M.9 Current regression coverage and failure policy

`test_character_motion_recovery.py` covers kind 0, all three synthetic bundled layouts, preservation of claimed source data, invalid body/gap rejection, unknown descriptor extras, exact ordinary INF sizing, corrupt legacy-animation rejection, actual MTN splitting, exact official MTM/IMM and A=4 reconstruction, source alias preservation, and continued failure of the two unresolved special types.

`test_character_archive_recovery.py` adds the integrated family/RES and stricter bounded-INF checks used for full-corpus recovery. ROM-dependent historical tests need their original private extracted fixtures; a missing fixture must not be reported as a proven format regression or a passing corpus comparison.

The corpus verifier processes each present XC independently, preserves original inputs, and checks conversion, selected RES magic, absence of newer animation extensions, XPCK repack/re-extraction equality, and output hashes when written. A successful companion slot does not make a failed slot successful. A missing slot is not created. A structural success is not a promise of correct appearance, playback, attachments, or other in-game behavior.

Unknown special forms stay conversion failures until an old-format comparison or controlled game experiment establishes a safe rule. The converter does not silently switch from failure to feature deletion; any future stripping policy would need a separate explicit design and implementation decision.

## Appendix C: Explicit p00 Copy and Auto CLI

### C.1 Policy selection, not failure fallback

The default behavior remains strict p00/p80/p84 conversion with a complete same-character trio. `--copy-p00` is an explicit alternate workflow: copy a present p00 **even when strict conversion could succeed**, and normally convert every selected p80/p84. It neither attempts model conversion nor falls back silently after an error.

The project author reports that unmodified YW3 p00 can run in B1. This motivates an explicit preservation option, but is author-provided evidence rather than new game verification by the converter developers. The 104 unresolved p00 cases in the historical strict audit remain **unsupported internal conversion cases**, not a verdict that their original archives cannot be transplanted unchanged.

### C.2 Bytes-layer and discovery contracts

```python
find_character_xc_files(input_path, *, allow_partial=False) -> dict[str, Path]
convert_character_xc_archives(archives, res_version=1, *, copy_p00=False) -> dict[str, bytes]
convert_character_xc_set(input_path, output_dir, res_version=1, overwrite=False, *, copy_p00=False) -> list[Path]
```

The set I/O function passes `allow_partial=copy_p00` into discovery and the same policy into the bytes layer. In normal mode, exactly three major archives are required. In copy mode, 1–3 are accepted. Both modes reject unsafe names, duplicate major slots, and selected major files with different case-insensitive character base names.

Directory discovery ignores non-major XC slots in both modes, including normal ROM directories that contain p10/p20 alongside the major trio. It rejects directories containing major slots for multiple characters. File discovery requires a major XC filename and selects only same-base major siblings. Neither mode recursively discovers every character or accepts a non-major selected file as a substitute.

### C.3 Copy validation and exact preservation

For a present p00 in copy mode, the bytes layer calls `unpack_xpck_archive` solely to validate the container, then returns the **original input archive bytes**. The unpacked dictionary is not passed to `convert_p00_internal_files` or the XPCK packer.

Container checks still include XPCK framing/ranges, filename decoding and CRCs, unique safe names, known RES compression and expanded CHRC magic, and the established archive placement/padding checks. Copy mode is not permission to copy a malformed container. It does not validate model semantics, PRM compatibility blocks, bone hierarchies, texture forms, LKAT internals, or the p00 RES reference graph.

Every original p00 byte is retained: compressed bytes, file order, internal filenames, unknown internal resources, RES generation, and archive padding. `--res-version 0/1` is applied only to converted motion slots in this mode. A source p00 with CHRC02 remains CHRC02; no claim of p00 CHRC00/01 output is made. Default strict p00 and standalone `p00-xc`/`p00-content` behavior is unchanged.

### C.4 Partial sets

Copy mode processes only present major slots:

| Selected input | Output |
|---|---|
| p00 only | One exact container-validated p00 copy |
| p00 plus p80 or p84 | Copy p00 and convert the present motion slot |
| p80 and/or p84 without p00 | Convert the present motion files; create no p00 |
| Complete trio | Copy p00 and convert both motion files |
| No major XC | Error |

This policy does not fill missing slots with B1 templates, rename another archive into a missing slot, or copy a failed motion file.

### C.5 Short automatic CLI

The normalization in `main` recognizes one `--auto` before the option terminator, removes it, and dispatches a bare input/output invocation to `character-xc`. More than one `--auto` is a usage error. Explicit `character-xc ... --auto` is accepted but redundant; another subcommand combined with `--auto` is a usage error.

Equivalent copy selections:

```powershell
python character_converter.py INPUT OUTPUT_DIRECTORY --auto --copy-p00
python character_converter.py character-xc INPUT OUTPUT_DIRECTORY --copy-p00
```

`--copy-p00` is an option of the character-set workflow, not of `p00-xc`, `p8-xc`, or internal-format commands. Existing overwrite, output-directory, filename, source-protection, and RES-version arguments retain their contracts. The short form adds no separate conversion implementation.

### C.6 Failure and writing guarantees

The chosen p00 operation and all selected motion conversions complete in memory before output staging. A malformed copied p00 container or any selected motion conversion error aborts the operation before new final files are written; pre-existing outputs remain untouched by that format error. `--overwrite` does not suppress validation errors and never authorizes modifying the source.

After preparation succeeds, the existing staged writing logic handles all selected 1–3 outputs under their original filenames. Its existing OS-level limitation remains: replacing several files in an already-existing destination directory is not a filesystem transaction, so an OS failure during replacement is distinct from an ordinary pre-write format failure.

### C.7 Motion failures remain strict

| XC | Problem internal file | Unsupported special form |
|---|---|---|
| `x611000_p80.xc` | `000.mtninf2` | Entry 2 descriptor 0: A=4/event `0x044E`, auxiliary value 0 |
| `x791000_p84.xc` | `000.mtninf2` | Entry 5 descriptor 0: A=16 |

Both remain conversion errors even with `--copy-p00`. Motion data is neither copied nor stripped as a fallback. Selecting either archive prevents new output of the entire selected set, including an otherwise valid p00 copy.

### C.8 Completion and runtime evidence

A successful copy-mode run means that the selected major filenames/bases were valid; every present p00 container passed the container checks and was preserved exactly; every present p80/p84 passed the normal conversion/repack checks; and the selected outputs were written under their original names. It does not mean all three slots existed, all RES files were downgraded, p00 model internals were supported, or every output works in B1.

The copy-mode CLI explicitly identifies p00 as `copied unchanged` or `not present` and lists only written files. The selected CHRC version in that message describes converted motion files, not copied p00. Hash equality verifies the copying contract; controlled game testing is still necessary for compatibility, appearance, attachments, and motion behavior.

### C.9 Copy-mode regression evidence

On 2026-10-15, all 104 historically unresolved p00 cases were exercised in memory with explicit copy mode. Each output p00 exactly matched the entire original XC byte sequence. Their available-slot compositions were 103 p00-only sets and one complete trio (`y740000`); present motion outputs matched ordinary motion conversion, and missing slots were not created. This verification did not save new XC files or modify source ROM/previous converted XCs, and it was not a game test.

`test_character_p00_copy.py` adds copy/partial/CLI/discovery, preservation, source-protection, and failure-policy regression coverage. The new 28 tests and the existing 39 recovery tests passed together (67 total). These checks verify implementation contracts; they do not establish runtime compatibility of all copied model internals.
