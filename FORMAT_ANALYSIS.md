# Character XC Format Analysis: Yo-kai Watch 3 to Yo-kai Watch Blasters

## 1. Purpose of This Document

This document records the analysis performed to convert Yo-kai Watch 3 (YW3) character XC archives into a format usable by Yo-kai Watch Blasters (YWB1). It is intended to remain understandable without reconstructing the work from implementation code or conversation history.

A character normally has three relevant XC slots.

| Slot | Primary role | Main internal files |
|---|---|---|
| `p00` | Model, bones, materials, textures, collision, and related data | `prm`, `atr`, `mtr`, `mbn`, `xi`, `txp`, `cmn`, `lkat`, `sil`, `RES.bin` |
| `p80` | Motions used mainly inside the Blasters House | `mtn3`, `mtninf2`, `cmn`, `RES.bin` |
| `p84` | Motions used mainly in battle and the Medallium | `mtn3`, `mtninf2`, `cmn`, `RES.bin` |

This is a **format-analysis reference**, not an implementation specification. It explains:

- XC/XPCK and internal-file structures.
- Generation differences between YW3 and YWB1.
- References between files.
- Which formats require conversion and which should be preserved.
- Exceptions and asset-content revisions found in the comparison corpus.
- The boundary between confirmed facts, strong inferences, and unknown details.

For implementation and operation, see:

- [Character converter implementation specification](./IMPLEMENTATION_SPEC.md)
- [Character converter user guide](./USER_GUIDE.md)

### 1.1 Recommended Reading Order

First read Sections 3 and 4 for the roles of `p00`, `p80`, and `p84` and their reference graph. Sections 5 through 7 describe the common XC, compression, and RES foundation. Sections 8 through 11 cover formats that are transformed between generations, while Sections 12 through 18 cover formats that are validated and preserved. Sections 19 through 22 summarize the conclusions and design reasoning.

In short, character XC archives reuse the same XPCK foundation as effect XC archives, but their internal formats are character-specific. The strict downgrade pipeline explicitly converts `mtn3`, `mtninf2`, `prm`, `lkat`, and `RES.bin`; shared formats retain YW3 content after structural validation. An explicit p00-copy workflow instead preserves the entire model XC without claiming internal conversion or complete model compatibility; see [Appendix C](#appendix-c-p00-preservation-and-runtime-evidence).

## 2. Evidence and Confidence Levels

### Full-Corpus Update (2026-10-14)

The initial ten paired characters remain the historical sample described below. The expanded corpus supplies 2,949 YW3 p00/p80/p84 archives and 1,626 matching-slot B1 archives (547 p00, plus 1,079 p80/p84). B1 also supplies six other XC files used only as reference evidence. Other YW3 slots are not conversion targets.

The 2026-10-14 strict-conversion audit structurally converted and repacked 2,843 target XC files: p00 1,060, p80 890, and p84 893. It left 106 unresolved: 104 p00 internal-conversion cases and two special motion cases. Of the original 637 failures, 531 were recovered; all 243 failures with same-named B1 archives were recovered. This is preserved as strict-conversion history, not a verdict that unchanged copies of the 104 model XCs cannot work in B1. A structurally successful archive has not thereby passed new in-game testing.

The updated model rules are stated in Sections 10 through 18 and in the integrated [model recovery analysis](#r2-model-format-recovery) and [XI recovery analysis](#r3-xi-format-recovery) in Appendix R. Appendix M documents expanded motion, compression, and RES rules. Model cardinalities are now variable: multiple textures/projections/LKAT are valid, and absent resource kinds are valid when their RES sections are absent. MBN and CMN remain mandatory in the supported p00 pipeline.

Unresolved topics include bone-less models (89 XC, overlapping with other topics), nonzero PRM tails, PRMGRP, model RES type `0x0123`, unverified XI `0x04`, CMN array element type 1, unique COLLISION_RECT size metadata, and two special MTNINF2 variants. Topic counts overlap; they are not an additive failure total. No unknown data is silently stripped.

### 2.1 Comparison Corpus

The primary binary comparison used ten characters extracted from both YW3 and YWB1, with 30 corresponding XC pairs.

```text
x001000
x302000
y001000
y199000
y267000
y290000
y318000
y344000
y407000
y473000
```

Each character has `p00`, `p80`, and `p84`.

```text
YW3  : 10 characters × 3 XC = 30 XC
YWB1 : 10 characters × 3 XC = 30 XC
```

The workspace also contains three YW3-only XC archives for `y773000`. Because no corresponding YWB1 files are available, they were not used for generation-to-generation byte comparison. All three nevertheless parse and convert successfully under the known structural rules.

### 2.2 Validation Method

Analysis and validation proceeded as follows.

1. Compare lengths, magic values, headers, offsets, record counts, and compression kinds between corresponding YW3 and YWB1 files.
2. Reverse CRC32 values through the RES string table to identify references that would otherwise remain numeric.
3. Compare compressed regions after decompression, separating compression differences from differences in logical data.
4. Apply the inferred conversion rules to all samples and compare generated structures with official YWB1 files.
5. Test individual p00, p80, and p84 conversion and complete three-file conversion.
6. Confirm that all three converted XC archives work in both an emulator and on real hardware.

### 2.3 Confidence Labels

- **Confirmed**: holds across the complete sample corpus and is also supported by generated output or in-game validation.
- **Strong inference**: CRC references, value ordering, and filenames support the interpretation, but no official type or symbol name is available.
- **Unknown**: sufficient rules exist to preserve and validate the file safely, but the formal meaning of individual bits or values has not been established.

Unless otherwise stated, values are little-endian and offsets are measured from `0x00`, the beginning of the relevant file.

## 3. Naming and Slots

### 3.1 Character Base Name

The base name follows this pattern:

```text
[one-letter category][six-digit character number]
```

Examples:

```text
y473000
x302000
```

Within the analyzed corpus, the prefix means:

| Prefix | Meaning |
|---|---|
| `y` | Playable-side character or Yo-kai |
| `x` | Boss-type character |

### 3.2 XC Name

The slot follows the base name.

```text
<character>_p00.xc
<character>_p80.xc
<character>_p84.xc
```

The base portion before `p00`, `p80`, or `p84` must match for all three archives converted together. Archives from different characters must not be mixed.

### 3.3 Internal Filenames

Each internal format has its own independent three-digit sequence.

```text
000.prm, 001.prm, ...
000.mbn, 001.mbn, ...
000.cmn, 001.cmn, ...
```

The number `000` does not imply that `000.prm` and `000.mbn` represent the same logical object. A number is the record order within the RES section for that extension.

## 4. Reference Graph

Character internal files cannot be fully validated in isolation. `RES.bin` is the central index.

```text
p00 RES.bin
  ├─ Material-side sections
  │    ├─ ATR
  │    ├─ MTR
  │    └─ XI
  └─ Node-side sections
       ├─ PRM
       ├─ MBN ──> parent MBN by CRC32
       ├─ SIL
       ├─ TXP ──> projection and material names by CRC32
       ├─ CMN ──> parameter name and sometimes bone name by CRC32
       └─ LKAT

p80 / p84 RES.bin
  ├─ shared character root "out_00"
  ├─ logical MTNINF names ──> 000.mtninf, 001.mtninf, ...
  └─ CMN parameters

MTNINF
  └─ motion name, playback range, and special-track information

MTN2
  └─ hash table, four tracks, descriptors, and keyframe data
```

Checksums are standard unsigned CRC32.

```text
crc = CRC32(raw_name_bytes) & 0xFFFFFFFF
```

The NUL terminator is excluded and the checksum is calculated over the raw name bytes stored in the file.

## 5. Outer XC/XPCK Format

Character XC uses the same `XPCK` container as effect XC.

### 5.1 XPCK Header

The header is 20 bytes.

| Offset | Size | Description |
|---:|---:|---|
| `0x00` | 4 | `XPCK` |
| `0x04` | 2 | Low 12 bits = `file_count`; high four bits = `index_bits` |
| `0x06` | 2 | Information-table offset / 4 |
| `0x08` | 2 | Compressed filename-table offset / 4 |
| `0x0A` | 2 | Data-region offset / 4 |
| `0x0C` | 2 | Information-table size / 4 |
| `0x0E` | 2 | Compressed filename-table size / 4 |
| `0x10` | 4 | Data-region size / 4 |

The high four-bit value is:

```text
index_bits = bit_length(file_count - 1)
```

### 5.2 Twelve-Byte Information Record

Each file has one 12-byte record.

```text
u32 filename_crc32
u16 filename_offset
u16 data_offset_div4_low
u16 file_size_low
u8  data_offset_div4_high
u8  file_size_high
```

Actual offset and size are reconstructed as:

```text
relative_data_offset = ((offset_high << 16) | offset_low) * 4
file_size            =  (size_high << 16) | size_low
```

Information records are in ascending filename-CRC32 order. A CRC32 collision cannot be represented safely and is forbidden inside one XPCK.

### 5.3 Filename Table

The filename table is a Level-5-compressed sequence of NUL-terminated UTF-8 names. `filename_offset` is relative to the beginning of the **decompressed** table.

XPCK is flat and internal filenames do not contain path separators.

### 5.4 Data Region and Padding

File payloads are placed on four-byte boundaries. Under the observed XPCK rule, even a file whose length is already divisible by four receives four zero bytes before the next file.

```text
padding_size = 4 - (file_size % 4)
```

Thus `file_size % 4 == 0` still produces `padding_size == 4`. This is not ordinary `(-size) % 4` alignment.

### 5.5 Outer Compression of RES.bin

Only `RES.bin` is Level-5-compressed at the XPCK layer. An extracted `RES.bin` is an uncompressed `CHRCxx` file.

The 30 compared YW3 XC archives used:

| Compression | Count | Archives |
|---|---:|---|
| Kind 1 / LZ10 | 28 | Ordinary cases |
| Kind 2 / Huffman4 | 2 | `y473000_p80.xc`, `y473000_p84.xc` |

All 30 YWB1-side RES payloads use kind 1 / LZ10. Repacking the uncompressed RES as LZ10 is readable in both the emulator and on hardware.

### 5.6 Repack Validation

The same uncompressed data can produce different LZ10 bytes depending on match selection. Correctness should be evaluated in this order:

1. XPCK tables, checksums, offsets, and sizes are internally consistent.
2. Re-extracted internal files match the pre-pack set.
3. Decompressed logical content matches.
4. The game loads the archive.

Whole-XC compressed-byte identity is not the only valid result.

## 6. Shared Level-5 Compression Information

The table below records the initial ten-pair corpus. Kind 0 and the full-corpus motion rules are covered in [Appendix M](#appendix-m-full-corpus-motion-update), which supersedes the initial-only restrictions.

The first 32 bits of a Level-5 block are:

```text
compression_kind = header & 7
raw_size         = header >> 3
```

Character XC analysis encountered:

| Kind | Name | Main uses |
|---:|---|---|
| 1 | LZ10 | RES, MTN, MTR metadata, XI image, converted special MTNINF |
| 2 | Huffman4 | Some RES files, MTR LUTC, XI tile table |
| 3 | Huffman8 | Seven MTN3 files and corresponding YWB1 MTN2 files |
| 4 | RLE | Some MTR LUTC blocks |

File-format generation and compression method are independent. A YW3 MTN3 can use LZ10 or Huffman8, so the kind alone does not identify YW3 or YWB1.

## 7. RES.bin

### 7.1 Shared Header

YW3 RES begins with `CHRC02`; YWB1 uses `CHRC00` or `CHRC01`.

```text
offset size description
0x00   6   "CHRC00", "CHRC01", or "CHRC02"
0x06   2   unknown0
0x08   2   string_table_offset / 4
0x0A   2   unknown1
0x0C   2   material_section_table_offset / 4
0x0E   2   material_section_count
0x10   2   node_section_table_offset / 4
0x12   2   node_section_count
```

The comparison corpus uses `unknown0=0` and `unknown1=1`, preserved between generations.

### 7.2 Section Descriptor

Material and node tables are arrays of eight-byte descriptors.

```text
struct ResSectionDescriptor {
    u16 data_offset_div4;
    u16 record_count;
    u16 type_id;
    u16 record_stride;
}
```

A normal section has:

```text
section_size = record_count * record_stride
```

Type `0x270F` is a data-free sentinel with count zero and stride zero.

### 7.3 String Table

The table concatenates NUL-terminated strings. An empty string begins the trailing zero padding, and the table is padded to a four-byte boundary.

Strings include:

- Material names.
- Mesh and node names.
- Bone names.
- CMN parameter names.
- Motion names.
- Texture-projection names.

Resolving internal-file CRC32 values through this table reveals their reference meanings.

### 7.4 Confirmed p00 Section Mapping

Across all ten pairs, section counts match internal-file counts and CRC references are consistent.

#### Material Side

| Type | Stride | Mapping | Confidence |
|---:|---:|---|---|
| `0x00DC` | 8 | ATR | Confirmed |
| `0x00E6` | 8 | MTR | Confirmed |
| `0x00F0` | 20 | XI | Confirmed |
| `0x0122` | 224 | Material body information | Strong inference |

#### Node Side

| Type | Stride | Mapping | Confidence |
|---:|---:|---|---|
| `0x0064` | 8 | PRM | Confirmed |
| `0x006E` | 8 | MBN | Confirmed |
| `0x0078` | 8 | SIL | Strong inference |
| `0x008C` | 8 | TXP; absent when the character has no TXP | Confirmed |
| `0x00C8` | 8 | CMN | Confirmed |
| `0x01CC` | 8 | LKAT; observed record name `HEAD` | Strong inference |

Numeric filenames follow record order in their section. Record zero of type `0x006E` is `000.mbn`, record one is `001.mbn`, and so on.

### 7.5 p80/p84 Converted Sections

The single `out_00` rule below describes the initial samples, not every character. [Appendix M](#appendix-m-full-corpus-motion-update) documents all six animation/INF categories, multiple logical roots, and stored-ID preservation.

p80 and p84 contain these YW3-generation section types.

#### Shared Character Root

| YW3 | YWB1 | Generated record |
|---:|---:|---|
| `0x012D` | `0x012C` | `CRC32("out_00"), 0` |

#### MTNINF Name List

| YW3 | YWB1 | Generated records |
|---:|---:|---|
| `0x0191` | `0x0190` | One `CRC32(mtninf_entry_name), 0` per entry |

The logical name is the raw byte sequence from each MTNINF2 body `+0x04` through the first NUL.

### 7.6 p00 RES Generation Difference

p00 has neither `0x012D` nor `0x0191`, so it does not need an internal section-type conversion. Its YW3 `CHRC02` is nevertheless rebuilt as YWB1 `CHRC00/01`.

| Result | Count |
|---|---:|
| Generated RES exactly matches official YWB1 | 8 |
| Difference caused by character-content revision | 2 |

The differing files are `x001000_p00` and `y001000_p00`. Their differences are revisions to material/node counts or content, not a section-format generation difference.

### 7.7 p80/p84 RES Results

For all 20 p80/p84 samples, rebuilding as CHRC01 with `0x012D -> 0x012C` and `0x0191 -> 0x0190` exactly matches official YWB1 RES.

When CHRC00 is selected, the current rebuilt output differs from CHRC01 only in the first six bytes.

## 8. p80/p84 MTN3 to MTN2

### 8.1 Role

`MTN` is likely an abbreviation of “motion,” based on the contents and use, although the official expansion is unknown.

YW3 uses `.mtn3`; YWB1 uses `.mtn2`. Both have `XMTN` magic. The generation difference is in the outer header and expanded internal-block placement.

### 8.2 YW3 MTN3 Outer Layout

This is the single-entry layout from the initial corpus. A generation-3 file can also bundle consecutive headers and shared decoded data; see [Appendix M](#appendix-m-full-corpus-motion-update) before applying these absolute offsets to another character.

| Offset | Size | Description |
|---:|---:|---|
| `0x00` | 4 | `XMTN` |
| `0x10` | 4 | Used data length `U` |
| `0x18` | 16 | Four descriptor-category counts, total `D` |
| `0x28` | 4 | Hash count `H` |
| `0x2C` | 44 | Name block |
| `0x58` | 4 | Probable frame count or playback length |
| `0x5C` | 8 | Four 16-bit track-related values |
| `0x64` | `16D` | YW3 descriptors |
| `0x64+16D` | Variable | Level-5-compressed internal block |

### 8.3 YW3 Expanded Block

```text
[H u32 hashes]
[four 8-byte track records]
[U bytes of actual data]
```

### 8.4 YW3 Descriptor

```text
struct Mtn3Descriptor {
    u32 flag_offset;
    u32 frame_offset;
    u32 value_offset;
    u32 extra;
}
```

The first three values are relative to the beginning of the YW3 actual-data area. The labels are descriptive; the complete type system of their targets remains unknown.

Every sample has `extra=0`. A future nonzero value must not be ignored.

### 8.5 YWB1 MTN2 Outer Layout

| Offset | Size | Description |
|---:|---:|---|
| `0x00` | 4 | `XMTN` |
| `0x04` | 4 | Zero |
| `0x08` | 4 | Runtime work-area size |
| `0x0C` | 4 | Name offset `0x28` |
| `0x10` | 4 | Compressed-block offset `0x58` |
| `0x14` | 20 | YW3 bytes `0x18..0x2B` moved here |
| `0x28` | 44 | YW3 name block |
| `0x54` | 4 | Frame-related value from YW3 `0x58` |
| `0x58` | Variable | Converted internal block |

### 8.6 YWB1 Expanded Block

```text
0x00 u32 hash_table_offset       = 12
0x04 u32 track_pointer_offset    = 12 + 4H
0x08 u32 descriptor_table_offset = 12 + 4H + 2×4 + 8×4

[H u32 hashes]
[four u16 track-record offsets]
[four 8-byte track records]
[D 16-byte YWB1 descriptors]
[U bytes of actual data]
```

Define:

```text
track_pointer_offset  = 12 + 4H
track_records_offset  = track_pointer_offset + 8
descriptor_offset     = track_records_offset + 32
target_data_offset    = descriptor_offset + 16D
```

Each 16-bit track pointer is:

```text
track_records_offset + 8 * track_index
```

### 8.7 Recalculating Descriptor Offsets

```text
new.flag_offset  = old.flag_offset  + target_data_offset
new.frame_offset = old.frame_offset + target_data_offset
new.value_offset = old.value_offset + target_data_offset
new.extra        = 0
```

The target values are absolute from the beginning of the expanded YWB1 block.

All samples match:

```text
work_size = len(target_raw) + 84D
```

The purpose of the additional 84 bytes per descriptor is unknown but appears to be runtime work storage allocated by YWB1.

### 8.8 Compression and Comparison Results

The 20 source MTN3 files use:

| Kind | Count |
|---:|---:|
| LZ10 / 1 | 13 |
| Huffman8 / 3 | 7 |

The corresponding official YWB1 MTN2 files have the same 13-to-7 distribution. Converted output may nevertheless be encoded entirely as LZ10.

Comparing the expanded generated data with official YWB1 gives:

| Category | Count |
|---|---:|
| Exact match | 3 |
| Same expanded size, different animation content | 13 |
| Different expanded size due to content revision | 4 |

These results indicate motion revisions between games, not an incorrect layout transformation. The converter preserves the YW3 motion content while arranging it in a YWB1-readable structure.

## 9. p80/p84 MTNINF2 to MTNINF

### 9.1 Bundled YW3 MTNINF2 Layout

YW3 stores multiple logical entries in one `.mtninf2`.

```text
[N 24-byte MINF headers]
[body 0]
[body 1]
...
[body N-1]
```

Headers are contiguous. The first location not beginning with `MINF` becomes body base `base`.

| Position in header | Size | Description |
|---:|---:|---|
| `+0x00` | 4 | `MINF` |
| `+0x08` | 4 | Body offset relative to `base` |
| `+0x14` | 4 | Special-track count, also copied to YWB1 `+0x18` |

Body offsets must be ascending. Each body ends at the next body offset; the last ends at EOF.

The first 68 body bytes form the normal region.

| Position in body | Description |
|---:|---|
| `+0x00` | Probable name hash |
| `+0x04` | NUL-terminated motion name |
| Following data | Playback range, frame and interpolation information, and fields not fully interpreted |

### 9.2 Normal YWB1 MTNINF

A normal output file is 96 bytes.

```text
0x00  "MINF"
0x04  0
0x08  0
0x0C  0x1C
0x10  0
0x14  0x60
0x18  four bytes from YW3 header +0x14
0x1C  first 68 bytes of YW3 body
0x60  EOF
```

All 177 normal 68-byte bodies copy without modification and exactly match official YWB1 MTNINF files.

### 9.3 Entry Counts

The 20 MTNINF2 files contain 244 entries.

| Slot | Entries | Normal 68-byte | Special |
|---|---:|---:|---:|
| p80 | 55 | 45 | 10 |
| p84 | 189 | 132 | 57 |
| Total | 244 | 177 | 67 |

### 9.4 YW3 Special-Body Layout

The initial A=8/A=12 dynamic forms remain valid. The additional A=4/event `0x05E4` rule and the two still-unsupported forms are documented in [Appendix M](#appendix-m-full-corpus-motion-update).

When a body is longer than 68 bytes, the region beginning at `body+0x44` is:

```text
[track_count 16-byte YW3 descriptors]
[track_count 12-byte fixed values]
[one 4-byte auxiliary value per dynamic descriptor]
[shared Level-5-compressed region, when present]
```

Each YW3 descriptor is:

```text
struct MtnInf2Descriptor {
    u32 payload_size;
    u32 shared_record_offset;
    u32 shared_payload_offset;
    u32 dynamic_count;
}
```

Two forms were observed.

#### Fixed Form

```text
dynamic_count = 0
payload_size = 0
shared_payload_offset = shared_record_offset
```

#### Dynamic Form

```text
dynamic_count = 1
payload_size = 8 or 12
shared_payload_offset = shared_record_offset + 4
```

The four-byte auxiliary value for each dynamic descriptor equals its `payload_size`.

At most one shared compressed region occurs in an MTNINF2. One entry contains that shared region but no descriptors of its own; it acts as a **carrier** providing data to other entries.

### 9.5 YWB1 Special Block

YWB1 expands and rebuilds the special data, then appends an LZ10-compressed form after MTNINF offset `0x60`.

Each YWB1 descriptor is 44 bytes.

```text
u32 record_length
u32 record_position
u32 payload_position
u32 marker = 0x00010000
u8  reserved[28] = 0
```

Record length is:

```text
record_length = 0x30 + payload_size + 4 * dynamic_count
```

The special block is:

```text
[44-byte descriptor × track_count]
[auxiliary values × total dynamic_count]
[expanded record for each track]
```

A fixed record is 48 bytes.

```text
[12-byte fixed value]
[36 zero bytes]
```

A dynamic record is:

```text
[12-byte fixed value]
[32 zero bytes]
[u32 dynamic_count]
[first four bytes of shared record]
[payload_size bytes of shared payload]
```

`payload_position` points after the initial four bytes of the shared record, at the actual payload.

Special MTNINF work size is:

```text
work_size = len(expanded_special_block) + 0x80 * track_count
```

### 9.6 Classification of the 67 Special Entries

| Category | Count | Result |
|---|---:|---|
| Fixed descriptors | 58 | Expanded generated data matches official YWB1 |
| Dynamic descriptors | 8 | Structure, numeric fields, and NUL-terminated strings match |
| Carrier | 1 | Produces a normal 96-byte file while supplying shared data |

Among the eight dynamic entries, official YWB1 strips the additional functionality from `x001000_p84_content/002` and reduces it to 96 bytes. The YW3 descriptor is nevertheless the same parseable dynamic form as the other seven, and the generated special block is structurally valid.

Some official pairs differ only in bytes after a NUL terminator. String equality is defined through the first NUL; unused padding after it is not treated as a semantic difference.

## 10. p00 PRM

### 10.1 Role

`PRM` appears to be a model primitive containing mesh vertices, indices, and skinning-related data. Internal regions include `XPRM`, `XPVB`, and `XPVI`.

### 10.2 Outer Header

| Offset | Description |
|---:|---|
| `0x00` | `XMPR` |
| `0x04` | Outer-header length `0x40` |
| `0x0C` | Generation-specific block start `S` |
| `0x10` | Generation-specific block end `E` |
| `0x40` | Internal magic `XPRM` |

The following fields are treated as offsets into later regions:

```text
0x10, 0x18, 0x20, 0x28, 0x30, 0x38
```

### 10.3 Generation-Specific Block

All 24 YW3 PRMs satisfy:

```text
E - S = 0x4C
data[E-16:E] = 16 zero bytes
```

YWB1 replaces the final 16 bytes with:

```text
00 00 00 00 01 01 00 00
```

The result is:

```text
converted block length = 0x44
converted file length  = source length - 8
```

Subtract eight from any original offset at least `E`. The XPRM data before `S` and all data after `E`, including XPVB/XPVI, remain unchanged.

### 10.4 Why Vertex Data Is Not Re-Rounded

Twenty-three of the 24 YW3 PRMs have an official YWB1 counterpart.

| Comparison | Count |
|---|---:|
| Generated file exactly matches official YWB1 | 8 |
| Compatibility block and later structure match, but official vertex values have rounding differences | 15 |
| No corresponding YWB1 file | 1 |

The unmatched source is:

```text
y001000/y001000_p00_content/001.prm
```

Official YWB1 vertex rounding appears to be an export-time asset difference, not a deterministic generation conversion recoverable from YW3. Re-rounding could unnecessarily change normals, weights, and positions. XPVB/XPVI are therefore preserved byte for byte.

## 11. p00 LKAT

### 11.1 Role

The name and `HEAD` reference suggest that `LKAT` stores look-at control data for the head or gaze.

### 11.2 Structure

The fixed header is `0x28` bytes, followed by `0x1C`-byte records.

| Offset | Size | Description |
|---:|---:|---|
| `0x24` | 2 | Record count `N` |
| `0x26` | 2 | Conversion-normalization value; formal runtime meaning remains unknown |
| `0x28` | `0x1C × N` | Records |

```text
file_size = 0x28 + 0x1C * N
```

YW3 `u16@0x26` values are:

| Value | Count |
|---:|---:|
| `0x3F80` | 6 |
| `0x0000` | 2 |
| `0x3F00` | 2 |

Every YWB1 file in the original ten-pair sample uses `0x3F00`. Replacing only these two bytes produces an exact official match for those ten pairs.

Seven files have four records; three files have two records.

Full-corpus inspection found one B1-only exception: `y275010/000.lkat` has bytes `04 CC 4C 3F` at `0x24`, whereas `y275000/000.lkat` has `04 00 00 3F`; the remaining header and four records match. This may be a packed low-byte count plus a float-related high-24-bit value, but that interpretation is unconfirmed. It is not evidence of corruption. All 1,038 supplied YW3 LKAT files still satisfy the implemented u16-count rule. The converter retains the previously selected `0x26 -> 0x3F00` normalization policy; matching initial pairs and prior game tests do not prove that this field is inherently a version tag. The exceptional B1-only file has no YW3 counterpart and is outside the current LKAT parser's coverage.

## 12. p00 SIL

### 12.1 Structure

`SIL` begins with `XCSL` and contains two `CMBC` sections.

| Offset | Size | Description |
|---:|---:|---|
| `0x00` | 4 | `XCSL` |
| `0x04` | 4 | Header length `0x20` |
| `0x10` | 4 | First CMBC offset |
| `0x14` | 4 | First CMBC length |
| `0x18` | 4 | Second CMBC offset |
| `0x1C` | 4 | Second CMBC length |

The following relationships hold:

```text
section1_end = section2_offset
section2_end = file_size
data[section1_offset:][:4] = "CMBC"
data[section2_offset:][:4] = "CMBC"
```

Six files are 188 bytes and four are 196 bytes. All ten pairs are byte-identical, so SIL is preserved after structural validation.

The formal expansion of `SIL` and the detailed meaning of CMBC remain unknown.

## 13. p00 ATR

### 13.1 Structure

The initial ten-character sample contained two compressed ATR encodings. Full-corpus comparison corrected their interpretation: the value at `0x0C` is a Level-5 compression header, not a fixed layout ID.

| Offset | Size | Description |
|---:|---:|---|
| `0x00` | 8 | `ATRC01\0\0` |
| `0x08` | 4 | Header length `0x0C` |
| `0x0C` | 4 | Level-5 header: decoded size in bits 3 onward, compression kind in low three bits |

| Identifier | Total length | YW3 count |
|---:|---:|---:|
| `0x01E3` | 40 | 10 |
| `0x01E4` | 36 | 9 |

`0x01E3` and `0x01E4` both specify 60 decoded bytes; they select Huffman8 and RLE respectively. The complete corpus also contains different compressed lengths, including 44, 48, and 52 bytes, without a new decoded layout. Validation now checks a 60-byte decoded block whose first u32 is 60. The table above records initial sample lengths, not universal format limits. Filenames and RES placement suggest material attribute data.

### 13.2 Generation Comparison

| Result | Count |
|---|---:|
| Corresponding YWB1 file exists | 18 |
| Exact match | 17 |
| Content/layout revision | 1 |
| No corresponding YWB1 file | 1 |

`y001000` is the exception.

- YW3 `000.atr` is 36 bytes; YWB1 `000.atr` is 40 bytes.
- YW3 `001.atr` has no same-named YWB1 file.

This is a material-composition revision, not a generation-wide ATR format change. Known layouts are validated and the YW3 ATR is preserved.

## 14. p00 MTR and LUTC

### 14.1 Role

MTR belongs to the material side of RES and contains LUTC blocks, suggesting a material container with lookup tables.

### 14.2 MTR Header

| Offset | Size | Description |
|---:|---:|---|
| `0x00` | 8 | `MTRC00\0\0` |
| `0x08` | 2 | Header length `0x18` |
| `0x0A` | 2 | LUTC 0 offset, or zero |
| `0x0C` | 4 | Zero |
| `0x10` | 2 | LUTC 1 offset, or zero |
| `0x12` | 2 | LUTC 2 offset, or zero |
| `0x14` | 4 | Zero |
| `0x18` | Variable | LZ10 metadata |

The initial ten-pair sample had nonzero LUTC offsets packed from the first slot. That is not a universal rule: the three fields are independent slots, and an absent first slot is valid in B1. Nonzero offsets must still be unique, ascending, four-byte aligned, and in bounds; see [Appendix R](#r2-model-format-recovery).

LZ10 expansion from `0x18` to the first LUTC, or to EOF when none exists, is 232 bytes in every file.

### 14.3 LUTC Block

| Offset | Size | Description |
|---:|---:|---|
| `+0x00` | 8 | `LUTC00\0\0` |
| `+0x08` | 4 | `0x00100000` |
| `+0x0C` | 4 | Zero |
| `+0x10` | Variable | Huffman4- or RLE-compressed data |

Every LUTC expands to `0x800` bytes. A block ends at the next LUTC offset or at MTR EOF.

In the observed files, the first LUTC uses RLE and following LUTC blocks use Huffman4.

### 14.4 YW3 Shape Distribution

| LUTC count | Typical total length | Count |
|---:|---:|---:|
| 0 | 88 | 9 |
| 2 | 3108 | 1 |
| 3 | 5140 | 9 |

### 14.5 Generation Comparison and Copy Policy

Eighteen of 19 YW3 MTR files have a YWB1 counterpart.

| Result | Count |
|---|---:|
| Exact match | 8 |
| Byte differences | 10 |
| No YWB1 counterpart | 1 |

In ordinary differences, the MTR header and 232-byte expanded metadata match, while expanded LUTC values differ. Some compressed files differ in length, such as 5140 versus 5144, while LUTC offsets and expanded sizes remain the same.

`y001000` has a material-composition revision.

- YW3 `000.mtr` is 88 bytes with no LUTC.
- YWB1 `000.mtr` is 5144 bytes with three LUTC blocks.
- YW3 `001.mtr` has no YWB1 counterpart.

These are LUT/material content revisions, not a YWB1 requirement for another MTR structure. MTR is validated internally and preserved to retain the YW3 appearance.

## 15. p00 MBN

### 15.1 Role and Fixed Structure

Matching RES node records, parent CRC references, and matrix-like float arrays identify MBN as model bone/node information.

Every file is `0xA8` (168) bytes.

| Offset | Size | Description |
|---:|---:|---|
| `0x00` | 4 | This node's name CRC32 |
| `0x04` | 4 | Parent node name CRC32; zero for the root |
| `0x08` | 4 | Flags |
| `0x0C` | 156 | 39 float32 values |

The individual meanings of the 39 floats are unknown. They likely contain node transforms, matrices, bind information, or related pose data.

### 15.2 Hierarchy Rules

All ten characters satisfy:

- Node CRC values are unique inside one XC.
- Only `000.mbn` has parent CRC zero and is the root.
- Every other parent exists in a lower-numbered MBN.
- MBN order matches record order in RES type `0x006E`.
- All 39 floats are finite.

All 285 YW3 flags are 4. Nearly all YWB1 flags are also 4, except `y407000/028.mbn`, which uses 12. Flag 12 appears to be node-specific rather than a generation difference.

The full corpus also establishes flag 5 in B1, including corresponding `y191000` and `y191010` nodes. The converter accepts 4, 5, and 12 and preserves all 39 floats without rounding. Tiny transform differences between generations remain asset data, not a reason to replace YW3 values.

### 15.3 Generation Comparison

| Result | Count |
|---|---:|
| YW3 MBN files | 285 |
| Corresponding YWB1 files | 282 |
| Exact matches | 62 |
| Differences | 220 |
| No same-named YWB1 file | 3 |

The three unmatched YW3 files are:

```text
x001000/032.mbn
y001000/021.mbn
y001000/022.mbn
```

Most differences are recalculation, rounding, or model revisions in the 39 floats. Node removal in some YWB1 assets also shifts the relationship between later numeric filenames and logical nodes.

The binary structure is shared between generations. Preserving the YW3 hierarchy requires copying every YW3 MBN; a node must not be deleted merely because official YWB1 lacks the same numeric filename.

## 16. p00 XI

### 16.1 Role

XI stores model textures. Its magic is `IMGC00`; the initial sample used ETC1 (`0x1B`). Full-corpus B1 examples also establish `0x1C` with 64 bytes per stored tile. YW3 format `0x04` has no B1 example and remains unsupported.

### 16.2 Header

| Offset | Size | Description |
|---:|---:|---|
| `0x00` | 8 | `IMGC00\0\0` |
| `0x08` | 2 | `0x30` |
| `0x0A` | 1 | Image format `0x1B` = ETC1 |
| `0x0B` | 5 | `01 01 04 20 00` |
| `0x10` | 2 | Width |
| `0x12` | 2 | Height |
| `0x14` | 4 | `0x30` |
| `0x18` | 4 | `0x00010030` |
| `0x1C` | 4 | Data offset `0x48` |
| `0x20` | 4 | `3` |
| `0x24` | 16 | Zero |
| `0x34` | 4 | Compressed tile-table size `T` |
| `0x38` | 4 | `align4(T)`; the initial sample's aligned `T` hid this distinction |
| `0x3C` | 4 | Compressed image-data size `I` |
| `0x40` | 8 | Zero |

### 16.3 Data Region

```text
0x48                         T bytes of Level-5 tile-table data
align4(0x48 + T)             I bytes of Level-5 image data
align4(image_start + I)      EOF
```

Expanded tile-table size is:

```text
tile_table_raw_size = width * height / 32
```

Full-corpus validation accepts Level-5 kinds 0 through 4 and checks the decoded u16 tile indices against the stored image tiles. For `0x1B`, expanded image length is in 32-byte units and no greater than `width * height / 2`; for `0x1C`, tile units are 64 bytes and the maximum doubles. The set of indices equals exactly `0..stored_tile_count-1`. The tile table maps tiles to stored image data rather than requiring a unique block for every tile position.

Only `x302000` uses 128×128; the other nine samples use 256×256.

### 16.4 Generation Comparison

| Result | Count |
|---|---:|
| Exact match | 5 |
| Revised image content | 5 |

The revised characters are:

```text
y199000
y290000
y318000
y344000
y407000
```

Header structure, compression, and tile-table rules are shared; only the image content changed. XI is validated and preserved to retain the YW3 model texture.

## 17. p00 TXP

### 17.1 Structure

TXP has a fixed length of 36 bytes.

```text
0x00 u32 texture_projection_name_crc32
0x04 u32 material_name_crc32
0x08 float32 values[7]
```

The first CRC matches a record in RES type `0x008C`, and both CRC values resolve through the RES string table.

Example:

```text
DefaultLib.x001000_01_01_texproj0
DefaultLib.x001000_01_01
```

The formal names of the seven floats are unknown. All eight samples contain:

```text
0, 0, 0, 0, 0, 1, 1
```

All eight characters with TXP have byte-identical YW3/YWB1 files. `y001000` and `y473000` have neither TXP nor a RES `0x008C` section. TXP is preserved after validation.

## 18. CMN

### 18.1 Role

CMN stores one named character parameter per file. The name likely abbreviates “common” or “common parameter.”

CMN appears in p00, p80, and p84.

| Slot | Count |
|---|---:|
| p00 | 159 |
| p80 | 95 |
| p84 | 96 |
| Total | 350 |

### 18.2 Twelve-Byte Scalar Form

```text
0x00 u32 value_bits
0x04 u32 parameter_name_crc32
0x08 u16 value_type
0x0A u16 element_count = 0
```

Observed scalar types are:

| Value type | Interpretation of `value_bits` |
|---:|---|
| 0 | float32 |
| 1 | u32, flag, enum, or CRC32 reference |

Type 1 meaning depends on the parameter name. For example, `mesh_sort` is an integer and `bb_ref_bone` is a bone-name CRC32.

### 18.3 Variable-Length Type 5

```text
0x00 u32 0
0x04 u32 parameter_name_crc32
0x08 u16 value_type = 5
0x0A u16 element_count = N
0x0C Element elements[N]

struct Element {
    u32 value_bits;
    u32 element_type;
}
```

Total length is:

```text
file_size = 12 + 8N
```

Observed element types are:

| Element type | Interpretation |
|---:|---|
| 0 | float32 |
| 2 | CRC32 referencing a RES string |

### 18.4 Size Distribution

| Total length | Count | Contents |
|---:|---:|---|
| 12 | 327 | Scalar; every p80/p84 CMN uses this form |
| 20 | 20 | Type 5 with one element |
| 68 | 3 | Type 5 with seven elements |

The 20-byte files are p00 `HEIGHT` and `COLLISION_CHARA`, one of each per character.

The 68-byte `SHADOW` form appears for `x001000`, `y290000`, and `y344000`. Its seven elements are:

```text
float scale_x
float scale_y
float scale_z
CRC32("c_c1"), element_type=2
float 0
float 0
float 0
```

Formal field names are unknown, but the values likely represent three-axis shadow scale, a reference bone, and auxiliary values.

### 18.5 Identified Parameters

| Name | CRC32 | Main type | Probable meaning |
|---|---:|---:|---|
| `HEIGHT` | `0x05B52289` | 5 | Character height |
| `bb_size_y_direct` | `0x0A47C297` | 0 | Direct Y size |
| `bb_size_z` | `0x0D3679CD` | 0 | Bounding-box Z size |
| `mesh_sort` | `0x202AEE27` | 1 | Mesh draw order |
| `COLLISION_CHARA` | `0x249DB393` | 5 | Character collision |
| `base_scale` | `0x516DB456` | 0 | Base scale |
| `bb_pos_z` | `0x57CE976B` | 0 | Bounding-box Z position |
| `bb_ref_bone` | `0x5CD1E566` | 1 | Reference-bone CRC32 |
| `bb_size_z_direct` | `0x84C8C574` | 0 | Direct Z size |
| `SHADOW` | `0x858E45AB` | 5 | Shadow settings |
| `chr_flag` | `0x8F06BAE5` | 1 | Character flags |
| `bb_size_y` | `0x943F2877` | 0 | Bounding-box Y size |
| `bb_pos_x` | `0xB9C0F647` | 0 | Bounding-box X position |
| `flw_cmr_type` | `0xBA3CEDA6` | 1 | Probable follow-camera type |
| `bb_size_x_direct` | `0xC6EDC209` | 0 | Direct X size |
| `bb_pos_y` | `0xCEC7C6D1` | 0 | Bounding-box Y position |
| `bb_size_x` | `0xE33818E1` | 0 | Bounding-box X size |
| `scale_base_one` | `0xF2B81B10` | 0 | Auxiliary base-scale value |

### 18.6 Relationship with RES `0x00C8`

Each RES CMN record is eight bytes.

```text
u32 parameter_name_crc32
u16 total_size
u16 extra_size
```

The final two fields are zero for every B1 12-byte scalar observed. YW3 `x024000/003.cmn` uniquely uses `(12,0)` for `COLLISION_RECT`; there is no B1 instance of that parameter. It remains unresolved rather than being silently normalized.

For type 5:

```text
total_size = complete CMN length
extra_size = complete CMN length - 12
```

Examples:

```text
20-byte CMN: total=0x14, extra=0x08
68-byte CMN: total=0x44, extra=0x38
```

Across all 350 files, RES record count, numeric filename order, name CRC, and variable-length metadata agree. The RES CMN reference section itself is byte-identical between YW3 and YWB1 in all 30 paired XC archives.

### 18.7 Generation Differences

Of 350 CMN files, 348 are byte-identical. The two differences are in `y001000_p00`.

| File | Parameter | YW3 | YWB1 |
|---|---|---:|---:|
| `002.cmn` | `bb_size_z` | 4.5 | Approximately 2.304302692 |
| `009.cmn` | `bb_size_y` | 7.0 | Approximately 6.711292267 |

Only values differ; name CRC, type, length, and RES references match. These are bounding-box content revisions, not format changes. The YW3 values belonging to the YW3 model are preserved.

## 19. Internal-Format Counts and Comparison Results

### 19.1 YW3 p00 File Counts

Totals across ten characters:

| Type | Count |
|---|---:|
| PRM | 24 |
| ATR | 19 |
| MTR | 19 |
| MBN | 285 |
| XI | 10 |
| TXP | 8 |
| CMN | 159 |
| LKAT | 10 |
| SIL | 10 |
| RES.bin | 10 |
| Total | 554 |

### 19.2 YW3 p80/p84 File Counts

| Type | p80 | p84 | Total |
|---|---:|---:|---:|
| MTN3 | 10 | 10 | 20 |
| MTNINF2 | 10 | 10 | 20 |
| CMN | 95 | 96 | 191 |
| RES.bin | 10 | 10 | 20 |

The MTNINF2 files split into 244 YWB1 MTNINF files.

### 19.3 Generation Comparison for Preserved Formats

| Type | YW3 count | Paired | Exact | Content difference | Unpaired |
|---|---:|---:|---:|---:|---:|
| ATR | 19 | 18 | 17 | 1 | 1 |
| MTR | 19 | 18 | 8 | 10 | 1 |
| MBN | 285 | 282 | 62 | 220 | 3 |
| XI | 10 | 10 | 5 | 5 | 0 |
| TXP | 8 | 8 | 8 | 0 | 0 |
| CMN (p00) | 159 | 159 | 157 | 2 | 0 |
| SIL | 10 | 10 | 10 | 0 | 0 |

A high number of content differences does not contradict the preserve policy. **Whether the binary format is shared** and **whether both games use identical asset content** are separate questions.

If the model, pose, LUT, texture, or collision values were revised without changing the format, copying YWB1 values would destroy the original YW3 asset. A YW3 value is preserved whenever its shared structure is readable by YWB1.

## 20. Downgrade Decision by Format

This table describes strict internal-format conversion. Explicit `--copy-p00` bypasses that entire model pipeline and preserves its source XC; it does not establish another internal-format downgrade rule. [Appendix C](#appendix-c-p00-preservation-and-runtime-evidence) distinguishes the two policies.

| YW3 input | YWB1 handling | Reason |
|---|---|---|
| `mtn3` | Re-encode as `mtn2` | Outer header and expanded-block layout differ |
| `mtninf2` | Split into multiple `mtninf` files and rebuild special data | Container and special-descriptor placement differ |
| `prm` | Reduce compatibility block `0x4C -> 0x44` and subtract eight from later offsets | Confirmed generation difference |
| `lkat` | Set `u16@0x26=0x3F00` | Exact result for all ten official pairs |
| `RES.bin` | `CHRC02 -> CHRC00/01`; downgrade two p80/p84 sections | Generation and reference sections differ |
| `atr` | Validated byte-identical copy | Same ATRC01 layouts in both generations |
| `mtr` | Validated byte-identical copy | Shared MTRC00/LUTC structure; differences are LUT revisions |
| `mbn` | Validated byte-identical copy | Shared 168-byte layout and hierarchy rules |
| `sil` | Validated byte-identical copy | All ten pairs are exact |
| `xi` | Validated byte-identical copy | Shared IMGC00/ETC1 structure; differences are image content |
| `txp` | Validated byte-identical copy | All eight pairs are exact |
| `cmn` | Validated byte-identical copy | Shared structure across 350 files; only parameter adjustments differ |

## 21. Why Conversion Order Matters

### 21.1 p00

```text
1. Parse RES.bin to obtain counts and CRC references for each extension.
2. Downgrade PRM.
3. Downgrade LKAT.
4. Validate and preserve ATR/MTR/MBN/SIL/XI/TXP/CMN.
5. Cross-check MBN hierarchy, TXP CRCs, and CMN CRC/length metadata against RES.
6. Rebuild RES as CHRC00/01.
7. Repack all files as XPCK.
```

### 21.2 p80/p84

```text
1. Convert MTN3 to MTN2.
2. Parse MTNINF2 and split it into individual MTNINF files while preserving logical names.
3. Validate and preserve CMN.
4. Rebuild RES 0x0191 as 0x0190 using the MTNINF name list.
5. Convert RES 0x012D to 0x012C.
6. Repack all files as XPCK.
```

Converting RES before parsing MTNINF2 would leave no source for the split MTNINF name list.

### 21.3 Complete Three-XC Conversion

p00, p80, and p84 are internally independent, but their shared character base name must be verified before they are processed together. One archive from another character can still be a valid XPCK and cannot be detected by generic XPCK validation alone.

## 22. Important Analytical Decisions

### 22.1 Official YWB1 Files Are Not a Value-Conversion Table

Official paired files mix true generation changes with:

- Vertex, normal, and weight rounding.
- Bone/node additions and removals.
- Revised motion content.
- Revised material LUT values.
- Revised texture images.
- Adjusted bounding-box values.

It would be incorrect to replace every differing YW3 byte with the corresponding YWB1 byte.

The correct classification is:

```text
Generation structure difference -> convert
Content difference in same format -> preserve YW3
Unknown form with unclear meaning -> reject instead of guessing
```

### 22.2 Do Not Reorder Numeric Files Independently

Names such as `000.mbn` are tied to RES section order. If YWB1 contains one fewer node, compacting or deleting later YW3 files would break RES references and the CRC hierarchy.

### 22.3 Separate Compression Differences from Logical Differences

Different compressed bytes can represent identical logical data. Conversely, MTR and XI include examples where expanded data itself differs, which is an asset-content revision.

### 22.4 Do Not Clear Unknown Fields

An unknown field is preserved when both generations use the same placement. Only confirmed YWB1 zero-reserved regions and newly generated fields specified by a rebuild rule are zeroed.

## 23. Remaining Unknowns

The following meanings are not formally established, although they do not prevent the current conversion.

- Official complete classifications represented by slot numbers `p00`, `p80`, and `p84`.
- Names and fields of the four MTN categories and eight-byte track records.
- Detailed data types of the flag/frame/value arrays referenced by MTN descriptors.
- Runtime purpose of 84 bytes per MTN descriptor.
- Every field in a normal 68-byte MTNINF body.
- Formal types of the special MTNINF 12-byte fixed value and 8/12-byte shared payload.
- All XPRM/XPVB/XPVI fields and the generation conditions for official YWB1 vertex re-rounding.
- Individual fields in each `0x1C`-byte LKAT record.
- Detailed CMBC structure inside SIL.
- ATR bit layout after `0x0E`.
- Meaning of the 232-byte MTR metadata and individual LUTC entries.
- Meaning of each of the 39 MBN floats and formal meaning of flag 12.
- Individual XI tile-table entry format and a complete reconstruction procedure for the sparse ETC1 image.
- Formal parameter names of the seven TXP floats.
- Official type names for CMN value type 1 and array element type 2.
- Unanalyzed RES section types and formal names of `unknown0` and `unknown1`.

When a new value or type is found, it must be analyzed as a new comparison sample rather than ignored or rounded into an existing value.

## 24. Probable Abbreviations

Without official debug symbols or specifications, these are hypotheses only.

| Extension | Probable expansion |
|---|---|
| MTN | Motion |
| MTNINF | Motion Information |
| PRM | Primitive or Parameter; content suggests model primitive |
| MBN | Model Bone or Model Node |
| MTR | Material |
| ATR | Attribute |
| XI | A Level-5 image format; formal expansion unknown |
| TXP | Texture Projection |
| CMN | Common or Common Parameter |
| LKAT | Look At |
| SIL | Probably Silhouette |
| RES | Resource |

These hypotheses improve readability but are not used as evidence for binary conversion rules.

## 25. Validated Range and Future Samples

The rules hold across ten paired characters, the additional unpaired YW3 character, emulator testing, and real-hardware testing.

Future characters may nevertheless contain:

- An unknown ATR decoded size, inner header, or compression kind; a different compressed length alone is not a new layout.
- Four or more LUTC blocks in MTR, or another compression kind.
- A new MBN flag.
- A non-ETC1 XI image format.
- Another TXP length.
- A new CMN value type or element type.
- A nonzero fourth MTN3 descriptor value.
- MTNINF2 `dynamic_count > 1` or another payload size.
- A new RES section type.

Rejecting an unknown form is a safety feature, not an arbitrary limitation: it prevents an incorrect conversion from hiding the real cause of a runtime failure. If a new sample triggers validation, analyze the matching YWB1 sample and reference relationships rather than disabling the check.

## 26. Final Conclusion

Character XC conversion is not a process of replacing every internal file with YWB1 values. It requires three classes of operation.

1. **Rebuild generation-specific structures**
   - MTN3 to MTN2.
   - MTNINF2 to individual MTNINF files.
   - PRM compatibility-block reduction.
   - LKAT compatibility-value change.
   - CHRC02 RES to CHRC00/01 RES.

2. **Validate and preserve shared formats**
   - ATR, MTR, MBN, SIL, XI, TXP, and CMN.

3. **Repack without breaking references**
   - Preserve RES order and numeric filenames.
   - Preserve CRC32 references.
   - Require matching p00/p80/p84 character base names.
   - Rebuild XPCK CRC order, compressed filename table, and four-byte placement rules.

The original sample p00/p80/p84 sets generated under this policy were confirmed in both the emulator and on real hardware. The later full-corpus expansions are structurally verified only; those new variants have not received new game or hardware confirmation.

## Appendix M: Full-Corpus Motion Update

### M.1 Scope and evidence boundaries

**Full-corpus recovery supersedes the initial-only restrictions** in Sections 6–9, 19–21, and 25–26. The original ten-pair counts and game-test results remain historical evidence; they are not removed or retrospectively redefined as tests of every newly supplied character.

The full corpus adds bundled `mtn3`, `mtm3`, and `imm3`, ordinary `mtminf2` and `imminf2`, already-old motion resources, optional LKAT/SIL in motion XCs, and Level-5 kind 0. The converter still handles only the selected p00/p80/p84 slots. It does not need to interpret p10/p20 or other slots to perform this conversion.

For motion recovery, every source from the first failed-motion group was inspected, and each available exact-name B1 XC was compared after extraction. In particular:

- `x003000_p80.xc`: converted MTM header and decoded payload match official B1 `000.mtm2` exactly.
- `x101000_p80.xc`: converted IMM header and decoded payload match official B1 `000.imm2` exactly.
- `x461000_p80.xc`: the YW3 `000.mtn3` contains two logical animations; B1 stores them as `000.mtn2` and `001.mtn2`.
- `x381000_p84.xc`: the additional A=4 special event reconstructs official B1 `011.mtninf` exactly after decompression.

Compressed-byte equality is not required. Where official B1 animation content has changed, the converter preserves YW3 data rather than substituting B1 motion values. Structural verification and a successful XPCK round trip do not establish game behavior for all new variants. The original emulator/hardware confirmation applies to the previously tested sample set; new full-corpus recovery outputs still need game testing.

### M.2 Level-5 kind 0

The shared four-byte header is unchanged:

```text
kind     = u32(header) & 7
raw_size = u32(header) >> 3
```

Kind 0 means **uncompressed**, not an unknown compressed stream. The next `raw_size` bytes are the decoded payload. The decoder requires `raw_size <= len(block) - 4` and returns exactly that slice. An advertised payload that extends beyond the input is invalid. Remaining archive/block padding is not part of the decoded payload.

The decoder now supports kinds 0–4: uncompressed, LZ10, Huffman4, Huffman8, and RLE. Kinds outside this set remain unsupported. Input compression does not identify format generation. Rebuilt generation-2 animations and expanded special MINF data are still emitted using LZ10; shared-format copied resources retain their original encoded bytes.

### M.3 Generation-3 animation bundles

The single-entry layout in Section 8 is a special case of this structure:

```text
[N consecutive animation headers]
[entry 0 name/frame/pointer/descriptor body]
...
[entry N-1 name/frame/pointer/descriptor body]
[one shared Level-5 block]
```

Each consecutive header starts with the family's magic. `body_base` is the byte immediately after the final consecutive header. Header and body offsets must be interpreted with the following family-specific sizes:

| Property | MTN3 | MTM3 | IMM3 |
|---|---:|---:|---:|
| Magic | `XMTN` | `XMTM` | `XIMA` |
| Header size per logical entry | 44 | 32 | 40 |
| Descriptor-count u32 fields from `0x18` | 4 | 2 | 4 |
| Track-category count `T` | 4 | 2 | 4 |
| Hash count `H` | `u32@0x28` | Sum of descriptor counts | Sum of descriptor counts |
| Used-data size `U` | `u32@0x10` | `u32@0x10` | `u32@0x14` |
| Decoded entry base `R` | `u32@0x14` | `u32@0x14` | `u32@0x10` |

All offsets in this table are relative to the start of that entry's header. Define `D` as the sum of its descriptor-category counts. The common header fields mean:

| Header field | Meaning |
|---|---|
| `u16@0x04` | Source pointer-region offset relative to `body_base` |
| `u16@0x06` | Source descriptor-table offset relative to `body_base` |
| `u32@0x08` | Decoded hash/track prefix size, exactly `4H + 8T` |
| `u32@0x0C` | Name-block offset relative to `body_base` |

Each body contains a 44-byte animation name block, a four-byte frame-related value, `2T` bytes of source pointers, and `16D` bytes of descriptors. Thus the pointer region must start 48 bytes after that entry's name start, and the descriptor table must start another `2T` bytes later. Bodies must be contiguous and in header order. The shared compressed block starts immediately after the last descriptor table.

Within the shared decoded block, one logical animation claims:

```text
[R, R + 4H + 8T + U)
```

Its prefix contains its own hashes and eight-byte track records; its remaining `U` bytes are the actual animation data. Bundled splitting checks that claimed regions are ordered, nonoverlapping, and in bounds. Unclaimed gaps and trailing decoded padding must be zero-filled. It does not merge different logical motions or copy another entry's hashes.

For `x461000_p80`, the two preserved name IDs are `0x03702B8A` (`out_00`) and `0xE0862685` (`x461000_p10_02001d_wkl`). Its former used-length failure came from treating the first header and the shared block as a standalone animation.

### M.4 Generation-2 output construction

Each logical source entry becomes a separate numbered file of the same family: `000.mtn2`, `001.mtn2`, and so on; MTM/IMM use their own independent numbering. All use the same decoded-table relocation formulas:

```text
pointer_start    = 12 + 4H
record_start     = pointer_start + 2T
descriptor_start = record_start + 8T
data_start       = descriptor_start + 16D
```

The first three target u32 values are `(12, pointer_start, descriptor_start)`. Each target u16 track pointer is `record_start + 8 * track_index`. Hashes, track records, and the claimed `U` source data bytes retain their original values. The three source descriptor pointers are relative to the actual-data area and become absolute target-decoded-block positions by adding `data_start`. The fourth descriptor field must be zero; an unknown nonzero value is rejected, not cleared.

| Output property | MTN2 | MTM2 | IMM2 |
|---|---:|---:|---:|
| Magic | `XMTN` | `XMTM` | `XIMA` |
| Work-size field | `0x08` | `0x10` | `0x08` |
| Name block / stored name ID | `0x28` | `0x24` | `0x24` |
| Compressed block | `0x58` | `0x54` | `0x54` |
| Work-size formula | `len(target_raw) + 84D` | Same | Same |

The animation name block contains a four-byte stored identity followed by 40 readable-name bytes. The frame-related value immediately precedes the target compressed block. The 84-byte runtime allowance is established by the old format; its precise runtime purpose is still unknown.

### M.5 Ordinary MTM/IMM information and bounded logical names

`mtminf2` and `imminf2` reuse the MINF container organization: consecutive 24-byte headers followed by body-relative entry areas. Each currently supported MTM/IMM information entry must have zero special-track count and **exactly 68 body bytes**. It becomes an ordinary 96-byte `mtminf` or `imminf`, using the same target common prefix as ordinary MTNINF. Additional payload or a special-track count is an unsupported form; it is not silently stripped or copied as though it were ordinary.

The logical INF name is distinct from both the physical numbered filename and the parent animation root. Its target common-region layout is:

| Target offset | Meaning |
|---:|---|
| `0x1C` | Stored CRC32 of the logical INF name |
| `0x20..0x4B` | 44-byte logical-name field |
| `0x4C` onward | Remaining common playback/reference fields |

The name must be nonempty and NUL-terminated **inside** the 44-byte field. A zero byte in subsequent playback fields cannot terminate an overlong name. The validator computes CRC32 over the raw bytes before that first NUL and requires it to equal `u32@0x1C`. Japanese names remain raw bytes; they are not decoded and re-encoded to compute CRC. This bounded CRC check applies to generated and copied `mtninf`, `mtminf`, and `imminf` files.

### M.6 One additional special MTNINF type, not a general relaxation

The existing fixed form and A=8/A=12 dynamic string forms remain as described in Section 9. The full-corpus comparison adds one narrowly supported form:

```text
payload_size A = 4
dynamic_count D = 1
shared_payload_offset = shared_record_offset + 4
event/type code in the corresponding 12-byte fixed value = 0x05E4
dynamic auxiliary value = 4
```

The event/type code is the last u32 of that fixed value. The generated expanded record length is `0x30 + 4 + 4 = 0x38`; the same existing position and work-size formulas apply. `x381000_p84` entry 11 reconstructs B1 `011.mtninf`'s common header and decoded special block exactly. Its four-byte non-string payload is preserved; the NUL-termination condition for A=8/A=12 strings does not apply. Its higher-level event meaning is not formally established.

This evidence does **not** permit every A=4 or every string length. The following source motion archives remain rejected:

| Source XC | Internal cause | Why no automatic rule is asserted |
|---|---|---|
| `x611000_p80.xc` | `000.mtninf2`, entry 2 descriptor 0, A=4/event `0x044E` | Its auxiliary value is zero and shared data is all zero; it is not the verified `0x05E4` form. No exact-name B1 XC is available. |
| `x791000_p84.xc` | `000.mtninf2`, entry 5 descriptor 0, A=16 | No exact-name B1 XC or corresponding A=16 expanded descriptor was found in the supplied B1 p80/p84 corpus. Extending the string-size formula alone does not establish compatibility. |

Neither case is converted by removing its special data. Unknown dynamic counts, nonzero descriptor extras, bad references, and inconsistent auxiliary values still cause failure.

### M.7 Already-old resources and optional LKAT/SIL

Some files supplied from YW3 already contain `mtn2` and individual `mtninf` together with `CHRC01`, rather than generation-3 bundles. `x492000_p80` is an example. These files must not undergo a second downgrade. Known v2 animation and ordinary/special INF structures are validated and their internal payloads copied byte-for-byte.

Validation checks target header offsets, reserved fields, bounded names, decoded table positions, descriptor ranges, and work-size formulas. Existing v2 animation copy requires the readable-name CRC to agree with its stored ID; the source alias exception below is not an unrestricted legacy-copy exception. Copied INF files always use the bounded logical-name CRC check in M.5.

An already-old `CHRC00`/`CHRC01` RES is parsed and its existing category references are compared against the actual internal files. It is then serialized with the selected output version. This is validated preservation of its reference values, not necessarily an unconditional byte-identical copy of the entire RES serialization.

Optional `lkat` and `sil` in p80/p84 use the same established standalone conversions as p00: LKAT compatibility-field conversion and validated byte-identical SIL copying. Their presence does not make the XC a model archive or change its motion conversion path.

### M.8 Six RES categories and physical versus logical records

The earlier `CRC32("out_00")` shortcut covers only the initial one-root MTN samples. Full archive conversion rebuilds every category from the actual source and converted internal files:

| Category | YW3 type / physical record | Old type / logical records | Identity source |
|---|---|---|---|
| MTN | `0x012D`, one 28-byte record | `0x012C`, one 8-byte record per `mtn2` | Stored ID at MTN2 `0x28` |
| IMM | `0x0137`, one 28-byte record | `0x0136`, one 8-byte record per `imm2` | Stored ID at IMM2 `0x24` |
| MTM | `0x0141`, one 28-byte record | `0x0140`, one 8-byte record per `mtm2` | Stored ID at MTM2 `0x24` |
| MTNINF | `0x0191`, one 28-byte record | `0x0190`, one 8-byte record per `mtninf` | CRC32 of each bounded logical INF name |
| IMMINF | `0x019B`, one 28-byte record | `0x019A`, one 8-byte record per `imminf` | Same |
| MTMINF | `0x01A5`, one 28-byte record | `0x01A4`, one 8-byte record per `mtminf` | Same |

The generation-3 section describes one **physical bundle**. It can correspond to several **logical animations**. Consequently, replacing only a type number or retaining a physical count of one is insufficient. Each old record is `(logical_identity_u32, 0)`, in the same order as that family's generated numbered files.

Converted files and their corresponding RES category must agree in presence, count, stride, order, and identifiers. Duplicate old/new categories, malformed old reserved words, absent required categories, or references to different internal files are errors. Names missing from the string table are appended while retaining its existing order and contents. The sentinel and section placement rules in Section 7 remain applicable.

### M.9 Renamed IMM aliases: preserve identity, do not repair by guessing

Official YW3 `y699000_p80` and `y699000_p84` IMM bundles are byte-identical to the respective official YW3 `y159000` bundles after reversing only the readable-name replacement `y699000 → y159000`. Their stored IDs retain the original y159000 identities. For example `FD9B443A`, `B82C643D`, `D056AB32`, and `C16CA308` match the original y159000 names' CRCs, not the renamed debug strings.

The downgrade preserves both the source stored IDs and readable names. RES uses the stored IDs; recomputing them from the renamed labels would introduce an identity change unsupported by the source data. Generated-v2 validation can therefore allow a nonzero source name-alias ID to differ from the readable-name CRC. Legacy v2 copy remains strict.

This is an **inference from official renamed source resources and the shared structure**, not a B1 game-test result. No same-name B1 y699000 XC was supplied. The available B1 v2 animations themselves have matching readable-name CRCs. These aliases should be included in future controlled in-game testing.

### M.10 Verification boundaries

The current motion regression suite covers bundled MTN/MTM/IMM splitting, used-data preservation, known compression including kind 0, rejection of nonzero unclaimed data and unknown descriptor fields, ordinary INF size checks, old-file validation, exact official MTM/IMM and A=4 reconstruction, alias preservation, and continued rejection of the two unresolved special forms.

The full-corpus check converts each existing p80/p84 XC independently, repacks it in memory, and requires re-extraction to equal the converted internal-file dictionary exactly. It checks the selected RES version and unchanged input bytes. This is useful even when a character has no p00 or is missing one motion slot. It does not infer a missing XC, replace failed output with an old success, or claim that structural success establishes gameplay compatibility.

## Appendix C: p00 Preservation and Runtime Evidence

### C.1 Unsupported conversion is not proven runtime incompatibility

The strict full-corpus audit's 106 unresolved XCs consist of 104 p00 internal-conversion cases and the two special motion cases in M.6. The 104 p00 cases lack a supported rule for some internal structure or reference relationship. That conclusion is narrower than saying their original model archives cannot be used in B1.

The user subsequently reports that unmodified YW3 p00 resources can work in B1. This is user-provided runtime evidence for allowing an intentional source-model preservation workflow. It is not new emulator/hardware verification performed during implementation, not a successful game test of every unresolved model, and not evidence that unknown PRM/RES/XI structures have acquired established downgrade rules.

The original structural analysis remains useful for the default strict pipeline and for investigating models that do not work when copied. A strict failure is still reported honestly; the alternate policy is not represented as a newly discovered binary conversion.

The 2026-10-15 implementation check exercised all 104 historically unresolved p00 cases in copy mode and found exact original-XC byte preservation for every model. The cases comprised 103 p00-only sets and one complete trio (`y740000`); existing motion outputs matched normal conversion and absent slots remained absent. This was an in-memory preservation test without new XC output or game testing, not a proof that those unknown internals are all B1-compatible.

### C.2 Exact container copy versus internal validated copying

The explicit `--copy-p00` policy checks a present p00's XPCK container using the established unpacker, then preserves the **complete original XC bytes**. It does not feed the extracted model resources to their converters and does not repack the archive.

| Property | Strict p00 conversion | Explicit whole-p00 copy |
|---|---|---|
| XPCK framing, names, CRCs, ranges, padding, and compressed RES | Validated | Validated |
| Model internal structures and cross-file references | Validated/converted under supported rules | Not model-validated or transformed |
| PRM/LKAT generation changes | Applied when required by the supported layout | Original bytes retained |
| p00 RES generation/version | Rebuilt as chosen CHRC00/01 | Original RES retained, including CHRC02 when present |
| XPCK serialization | Repacked and round-trip checked | Original input serialization copied exactly |
| Runtime compatibility of a new model | Must be tested in game | Must be tested in game |

This differs from the internal-format “validated copy” rules for ATR, MTR, MBN, XI, TXP, CMN, or SIL. Those rules validate each known internal format. Whole-p00 copy validates the container only; it intentionally preserves even internal structures that strict model conversion does not support. It is not a malformed-XPCK bypass.

The policy always copies a present p00 when selected, including models strict mode could convert successfully. It is not an automatic try-convert/then-copy fallback. No name ID, internal file, reference, unknown field, or source padding is modified to make the copied model resemble B1 output.

### C.3 Motion conversion and missing archives

`--copy-p00` changes only the p00 operation and permits an incomplete major-slot set. Every present p80/p84 still undergoes the normal strict motion conversion and RES rebuild. The selected RES version affects only converted motion files; it never changes a copied p00.

If p00 alone exists, the output is that exact p00 copy. If p00 is absent, the existing p80/p84 files can still be converted. Missing major files are not synthesized, filled from B1, or replaced by unrelated slots. In normal mode without this flag, a complete p00/p80/p84 trio is still required and p00 is strictly converted.

Both workflows select only principal p00/p80/p84 XCs and ignore p10/p20 and other XC slots. Directory input requires the selected major files to belong to one character. File input selects the same-base major siblings. Ignoring an out-of-scope file is not a conversion result for that file.

### C.4 The two unresolved motion types are unchanged

| Source XC | Problem internal file | Unsupported form |
|---|---|---|
| `x611000_p80.xc` | `000.mtninf2` | Entry 2 descriptor 0: A=4/event `0x044E`, auxiliary value 0 |
| `x791000_p84.xc` | `000.mtninf2` | Entry 5 descriptor 0: A=16 |

These files remain unconvertible under the established rules. The p00-copy policy neither strips their special events nor copies their generation-3 motion files unchanged. A selected set containing either fails before new selected outputs are written; another valid copied model does not suppress that error.

### C.5 Evidence to collect from copied models

Equal input/output XC hashes verify exact copying; container checks verify the archive can be parsed. Neither establishes that B1's model loader interprets all copied internals as intended. Record actual game observations separately: whether the model appears, textures and materials are correct, attachments/bones behave correctly, and its converted motion slots play as expected.

For failures, retain the copied source filename, command/options, error or visible behavior, affected slot, and any comparable B1 layout evidence. That information can distinguish a missing internal downgrade rule from a model-content issue without retroactively calling all strict failures impossible to transplant.

## Appendix R: Full-Corpus Model and XI Recovery

### R.1 Scope, evidence origin, and how to read the results

This appendix integrates the model and XI recovery findings into this public reference. No separate recovery document, audit JSON, extracted fixture, ROM file, or conversation transcript is required to understand the rules below. The original ten-pair tables elsewhere in this document remain historical evidence; the full-corpus rules here supersede initial-only assumptions, not the original measurements.

The measurements come from read-only analysis of the privately supplied YW3 and B1 character ROM corpora on 2026-10-14. The YW3 target corpus contained 1,164 p00 XCs. B1 contained 547 p00 XCs and 1,632 XCs across all supplied slots. B1's other slots were inspected only when they could establish a format's existence in the old engine; they were not added to the conversion scope.

| p00 internal format | YW3 files examined | B1 files examined |
|---|---:|---:|
| ATR | 2,280 | 1,138 |
| MTR | 2,280 | 1,138 |
| MBN | 32,715 | 16,504 |
| PRM | 3,086 | 1,500 |
| XI | 1,583 | 762 |

The first comparison key was the same XC name and the same internal filename. When no same-named B1 asset existed, a known B1 layout could still establish shared structure, but it could not establish that the assets had identical content or had been game-tested. Float differences, LUT revisions, and texture changes are not replaced with B1 values merely to obtain a byte match.

| Formerly rejected model topic | Internal files affected | XCs containing that internal failure | Strict handling after analysis |
|---|---:|---:|---|
| Variable ATR compressed length | 65 | 63 | Validate decoded structure, then copy unchanged |
| Empty MTR LUT slots | 38 | 38 | Validate independent slots, then copy unchanged |
| MBN flag 5 | 9 | 5 | Accept this B1-proven flag, then copy unchanged |
| Existing legacy PRM block | 3 | 1 | Validate the known old layout, then copy unchanged |
| Unknown nonzero PRM tail | 14 | 11 | No established strict conversion rule |
| PRMGRP | 11 | 11 | No established strict conversion rule |

These topic counts overlap and are not an additive XC failure total. Resolving one internal validation failure does not imply that every other resource in the XC also passes. XI recovery counts are detailed separately in R.3.

The strict full-corpus audit's 104 unresolved p00 cases are historical **internal-conversion** limitations. They are not proof that the unchanged source models cannot run in B1. The subsequent user report that original p00 models can work motivates the explicit whole-p00 preservation policy in [Appendix C](#appendix-c-p00-preservation-and-runtime-evidence). That policy neither establishes missing downgrade rules nor means every one of these variants has passed a game test. In particular, internal validated copying and whole-container copying have different guarantees.

### R.2 Model-format recovery

#### R.2.1 ATR: compression headers, not fixed-length layout IDs

The initial validator interpreted the value at 0x0C as a layout ID and required a 40-byte file for 0x1E3 or a 36-byte file for 0x1E4. The full corpus disproves that interpretation. A Level-5 compressed block starts at 0x0C:

| Offset | Size | Meaning |
|---|---:|---|
| 0x00 | 8 | `ATRC01\0\0` |
| 0x08 | 4 | Compressed-block start/header length, 0x0C |
| 0x0C | 4 | Level-5 header: `decoded_size << 3 | compression_kind` |
| 0x10 onward | Variable | Compression-specific tree, controls, and stream |

```text
0x1E3 = (60 << 3) | 3    # Huffman8, decoded length 60
0x1E4 = (60 << 3) | 4    # RLE, decoded length 60
decoded_u32_at_0 = 60
```

YW3 files have lengths 36, 40, 44, 48, and 52; B1 has lengths 36, 40, 44, and 48. The 52-byte YW3 examples lack a same-named B1 asset, but decode to the same 60-byte structure with the same inner size field. Their larger compressed stream is not evidence of an additional section.

Validation requires the correct magic and 0x0C header length, compression kind 3 or 4, declared decoded size 60, actual decoded size 60, decoded first u32 equal to 60, and four-byte file alignment. It does not infer a decoded layout from compressed file length. Decompression is for validation only; the original compressed bytes are retained.

Of the 65 formerly rejected ATR files, 30 are byte-identical to same-named B1 files. Direct examples are `x181000_p00.xc/000.atr` (48 bytes, Huffman8), `y234000_p00.xc/001.atr` (44 bytes, Huffman8), and `y155000_p00.xc/001.atr` (44 bytes, RLE). All decode to 60 bytes.

#### R.2.2 MTR: three independent LUT slots

The u16 fields at 0x0A, 0x10, and 0x12 specify independent LUTC slots. The old requirement that nonzero offsets be left-packed was incorrect. B1 `y133800_p00.xc`, `y191000_p00.xc`, and `y191010_p00.xc` all contain `002.mtr` with offsets `[0, 92, 2128]`. A missing first slot does not invalidate later slots.

YW3 `x602000_p00.xc/000.mtr` uses `[0, 92, 0]`. This exact occupancy pattern has no supplied B1 example, but the independent slots, metadata, LUTC header, and decoded LUT size follow the established shared structure. It is accepted without moving the remaining LUT to another slot.

The checks retained after removing the left-packing assumption are:

- Header magic `MTRC00\0\0`, header size 0x18, zero reserved regions, and four-byte file alignment.
- Nonzero offsets are unique, ascending, four-byte aligned, and within the file.
- Metadata occupies 0x18 through the first nonzero offset, or through EOF when all slots are absent. Its LZ10 stream decodes to 0xE8 bytes.
- Each LUTC extends through the next nonzero offset or EOF. It has `LUTC00\0\0`, u32@+0x08=0x00100000, u32@+0x0C=0, and a Huffman4/RLE stream at +0x10 decoding to 0x800 bytes.

YW3 and B1 may use different compressed bytes or trailing alignment lengths while sharing this structure. No LUT values or slot identities are rewritten to match B1's exported asset.

#### R.2.3 MBN: flag 5 is an established B1 value

The fixed layout remains 0xA8 bytes: node ID CRC32 at 0x00, parent ID at 0x04, flags at 0x08, and 39 float32 values at 0x0C. B1's 16,504 files use flag 4 in 16,489 cases, 12 in 11 cases, and 5 in four cases.

The flag-5 evidence is `024.mbn` and `026.mbn` in both `y191000_p00.xc` and `y191010_p00.xc`. Across the four corresponding YW3/B1 pairs, the first 12 bytes, total size, and float placement agree. Float values differ by up to approximately 1.87e-7, so these are not whole-file byte matches.

The supported flag set is `{4, 5, 12}`; unknown flags remain rejected. Nonzero node IDs, finite float values, RES node-ID agreement, unique node IDs, exactly one root at `000.mbn`, and parents appearing earlier remain checked. YW3 transforms are copied without re-rounding or substituting B1's values.

#### R.2.4 PRM: distinguish generation-3, already-old, and unknown tails

The normal downgrade from Section 10 still applies when `E-S=0x4C` and `data[E-16:E]` consists of 16 zero bytes. It replaces them with `00 00 00 00 01 01 00 00`, reduces the block to 0x44, and subtracts eight from the six later offset fields whose old values are at least E. Vertex/index payloads and all other preserved regions are not re-rounded.

YW3 `x492000_p00.xc` already contains the old 0x44 block in `000.prm`, `001.prm`, and `002.prm`. Every one of the 1,500 supplied B1 PRMs also has that block size and the same eight-byte marker. This already-old form is validated and returned unchanged; applying the eight-byte reduction again would corrupt it.

Legacy validation checks XMPR/XPRM, the 0x40 outer header, bounded generation block, 0x44 block length, the exact known marker, ordered name/material-name positions after the block, and name lengths within their regions. An unknown marker is not treated as proof of an already-compatible PRM.

Fourteen other YW3 PRMs have a nonzero u32 at the beginning of the final 16 bytes of the 0x4C block; the remaining 12 bytes are zero. Values 1 and 8 have no established old-format meaning. The strict converter continues to reject them rather than silently deleting those values; the exact source list is in R.4.

#### R.2.5 p00 cardinality and references: the initial sample was not exhaustive

One texture, one LKAT, one SIL, and at most one TXP were initial-sample properties, not universal archive rules. B1 also contains models with multiple textures/projections/LKAT resources and models without some resource kinds. For example, B1 `x591010_p00.xc` supplies bones, CMN parameters, and LKAT rather than an ordinary complete mesh/material set.

The strict supported model path requires MBN and CMN. Other known kinds may be absent or have multiple numbered files, but each kind's filenames must be contiguous from `000`, and the matching RES section must agree in presence, stride, and count. A missing file kind requires its corresponding RES section to be absent; it is not permission to ignore stale references.

| Internal kind | RES side | Type | Record stride |
|---|---|---:|---:|
| ATR | Material | 0x00DC | 8 |
| MTR | Material | 0x00E6 | 8 |
| XI | Material | 0x00F0 | 20 |
| PRM | Node | 0x0064 | 8 |
| MBN | Node | 0x006E | 8 |
| SIL | Node | 0x0078 | 8 |
| TXP | Node | 0x008C | 8 |
| CMN | Node | 0x00C8 | 8 |
| LKAT | Node | 0x01CC | 8 |

CMN parameter-name CRCs must still agree with their numbered RES records and resolve in the RES string table. The scalar/array sizes in Section 18 still apply. However, an array's type-2 value may reference an object outside that local string table. Native B1 `x003000_p00.xc/016.cmn` and `017.cmn` (`MESH_DRAW_ALP0`) and `x551020_p00.xc/009.cmn` (`SHADOW`) establish such external references. The old requirement that every type-2 value appear in the same RES string table was too strict.

The replacement check keeps the established element type and nonzero CRC validation, but leaves external object resolution to the game context. It does not change or invent the referenced ID, and does not relax the separate requirement that the CMN parameter's own name resolve locally. Unknown array element type 1 is a different unresolved topic, not an instance of the accepted type-2 external-reference case.

### R.3 XI-format recovery

#### R.3.1 Coverage and paired evidence

| Read-only corpus | XCs examined | XI files | Structurally validated identical copies | Strictly unsupported |
|---|---:|---:|---:|---:|
| YW3 p00 | 1,164 | 1,583 | 1,582 | 1 |
| B1 p00 | 547 | 762 | 762 | 0 |
| All supplied B1 XCs, including reference-only other slots | 1,632 | 768 | 768 | 0 |

Here “identical copy” means that validation returns the same bytes as its own input, not that YW3 and B1 textures are always identical. No out-of-scope B1 XC was converted or emitted.

Among 525 characters with same-named p00 archives, all 735 same-named XI pairs were compared. Of these, 446 match as complete files. All 735 agree in image-format value and dimensions; observed header differences occur only at the size-value bytes 0x34/0x35/0x38/0x39/0x3C/0x3D. Decoded tile tables match in 448 pairs and decoded image streams in 446 pairs. These comparisons establish shared framing with asset-content revisions, not an across-the-board relocation of image sections.

The original validator's three excessive restrictions were that u32@0x38 duplicate u32@0x34 exactly, that tile tables use only Huffman4 and image streams only LZ10, and that image format be limited to 0x1B. The corrected checks preserve the source XI bytes; they do not transcode pixels or recompress either stream.

#### R.3.2 Header, actual lengths, and aligned spans

The common XI header is:

| Offset | Size | Value or meaning |
|---|---:|---|
| 0x00 | 8 | `IMGC00\0\0` |
| 0x08 | 2 | 0x30 |
| 0x0A | 1 | Image format |
| 0x0B | 5 | Format-specific fields in R.3.4 |
| 0x10 / 0x12 | 2 each | Width W / height H |
| 0x14 | 4 | 0x30 |
| 0x18 | 4 | 0x00010030 |
| 0x1C | 4 | Data start 0x48 |
| 0x20 | 4 | 3 |
| 0x24 | 16 | Zero reserved bytes |
| 0x34 | 4 | Actual compressed tile-table length T, including its compression header |
| 0x38 | 4 | Aligned tile-table region length `align4(T)` |
| 0x3C | 4 | Actual compressed image length I, including its compression header |
| 0x40 | 8 | Zero reserved bytes |

```text
align4(n)   = (n + 3) & ~3
tile_start  = 0x48
tile_end    = tile_start + T
image_start = align4(tile_end)
image_end   = image_start + I
EOF         = align4(image_end)
```

Every one of the 1,583 YW3 p00 XIs and 762 B1 p00 XIs satisfies `u32@0x38=align4(T)`. T is not a multiple of four in 229 YW3 cases and 71 B1 p00 cases. For example, YW3 `x123000_p00.xc/000.xi` has T=1,258 and an aligned region length of 1,260. Requiring the two fields to be equal wrongly rejects this ordinary padding case.

Padding between `tile_end` and `image_start`, and between `image_end` and EOF, must be zero. Computed EOF must equal the actual file length; reserved bytes and fixed header values are also checked.

#### R.3.3 Decoded tile references, including legitimate duplicates

W and H must be positive multiples of eight. The decoded tile table is a little-endian u16 array:

```text
tile_table_raw_size = W * H / 32
tile_entry_count    = W * H / 64
stored_tile_count N = decoded_image_length L / bytes_per_stored_tile B
```

L must be positive and divisible by B, and N must not exceed `W*H/64`. The set of tile-table indices must be exactly `{0, 1, ..., N-1}`. This rejects out-of-range image references and unreferenced stored tiles, while allowing repeated indices. An image can reuse a stored tile at multiple visible positions; the stream need not contain a distinct block for every table entry.

These reference checks strengthen validation while compression kinds and image formats are broadened. Checking only that L is below a maximum would not detect all invalid references.

#### R.3.4 Established formats and the unverified format

| Format at 0x0A | Fields at 0x0B..0x0F | Stored tile B | YW3 p00 count | B1 p00 count | Strict handling |
|---|---|---:|---:|---:|---|
| 0x1B | `01 01 04 20 00` | 32 bytes | 1,567 | 759 | Validate and copy unchanged |
| 0x1C | `01 01 08 40 00` | 64 bytes | 15 | 3 | Validate and copy unchanged |
| 0x04 | `01 01 10 80 00` | 128 bytes, observed | 1 | 0 | No established B1 support; reject in strict mode |

The initial reference calls 0x1B ETC1. A formal name for 0x1C is not inferred solely from the numerical format fields; its observed format value and tile size suffice for the validated-copy rule.

B1 `x305000_p00.xc`, `x305010_p00.xc`, and `x305020_p00.xc` each contain format-0x1C `001.xi`. `x305000_p00.xc/001.xi` is completely identical between generations: 64×64, a 128-byte decoded tile table, a 2,880-byte decoded image, maximum index 44, and 45 stored tiles. This is direct old-engine format evidence rather than an assumption that every YW3 texture format is supported.

For 0x1B, `L <= W*H/2`; for 0x1C, `L <= W*H`. These bounds follow from the respective 32- and 64-byte tiles and `N <= W*H/64`, not from independent guessed image-size constants.

#### R.3.5 Compression variants and strength of evidence

Both streams use the common Level-5 header: low three bits select the kind and the upper 29 bits declare decoded length. Each is decoded for validation using kinds 0 through 4 as defined in Appendix M and Section 6, then copied without recompression.

| Kind | Method | YW3 p00 tile tables | B1 p00 tile tables | YW3 p00 images | B1 p00 images |
|---|---|---:|---:|---:|---:|
| 0 | Uncompressed | 20 | 7 | 1 | 1 |
| 1 | LZ10 | 236 | 72 | 1,503 | 723 |
| 2 | Huffman4 | 1,261 | 660 | 74 | 35 |
| 3 | Huffman8 | 9 | 6 | 3 | 3 |
| 4 | RLE | 57 | 17 | 2 | 0 |

Specific evidence includes:

- `x101000_p00.xc/001.xi`: kind-0 tile table and kind-2 image, also present in B1.
- `x122010_p00.xc/000.xi`: kind-1 tile table, with the aligned-span rule also needed in B1.
- B1 `x301000_p00.xc/000.xi`: kind-3 tile table and kind-1 image.
- `x381000_p00.xc/004.xi`: kind-4 tile table and kind-1 image, also present in B1.
- `x381000_p00.xc/006.xi`: both streams kind 0; the full files match between generations.
- `x491010_p00.xc/004.xi`: kind-2 tile table and kind-3 image, also present in B1.
- YW3 `x452000_p00.xc/000.xi` and `x601000_p00.xc/003.xi`: kind-4 image streams.

The final two RLE-image examples have no same-position B1 character-image evidence. However, RLE itself appears in 17 B1 p00 tile tables, uses the same common decoder, and those two YW3 image streams decode to established 32-byte tiles with valid complete references. Accepting their validated preservation is an inference from shared compression and image structure, not a new B1 rendering test. This is a narrower uncertainty than an image format with no B1 example at all.

#### R.3.6 What XI recovery does and does not count

In the original 637-failure audit, XI was the first reported cause in 100 XCs; that cause was resolved in 99. Independent diagnostics also exposed XI problems hidden behind earlier failures: 295 of 296 XCs with an XI problem had that problem resolved. These are XI validation recoveries, not counts of whole XCs converted successfully. The remaining source is the format-0x04 file in R.4.

Twelve XI regression tests covered both established image formats, kinds 0–4, unaligned actual compressed lengths, repeated indices, out-of-range references, unreferenced stored tiles, dimension mismatches, malformed format fields, unknown compression, invalid reserved bytes, truncation, nonzero padding, and continued strict rejection of 0x04. Corpus-dependent checks used the private original files; their absence in a public checkout is not represented as new passing binary comparisons.

### R.4 Historical strict-model limitations: exact affected sources

The following lists record missing internal downgrade/validation rules. They remain relevant to strict p00 conversion and to diagnosing a copied model that does not behave correctly. Explicit whole-p00 copying preserves these structures without claiming to convert them; see Appendix C. The groups overlap, especially PRM/UMBRELLA and bone-less/PRMGRP/0x0123, so their sizes must not be added as a failure total.

#### R.4.1 Nonzero PRM tail: 14 files in 11 p00 XCs

Each listed PRM has an otherwise 0x4C generation block whose final 16 bytes begin with the shown little-endian u32, followed by 12 zeros. No same-named B1 p00 was supplied for these cases. The field's meaning and old-format representation remain unknown.

| Source p00 XC | Internal PRM | First u32 of final 16 bytes |
|---|---|---:|
| x614000_p00.xc | 001.prm | 1 |
| y002000_p00.xc | 000.prm | 1 |
| y351100_p00.xc | 000.prm | 1 |
| y351110_p00.xc | 000.prm | 1 |
| y664020_p00.xc | 002.prm | 1 |
| y664030_p00.xc | 001.prm | 1 |
| y664100_p00.xc | 001.prm | 1 |
| y665000_p00.xc | 002.prm / 003.prm | 1 / 8 |
| y665010_p00.xc | 002.prm / 003.prm | 1 / 8 |
| y665020_p00.xc | 001.prm / 002.prm | 1 / 8 |
| y665030_p00.xc | 000.prm | 1 |

Deleting the nonzero word, or replacing it with an arbitrary old marker, would silently discard source information. Resolution needs a comparable old representation or evidence from the loader of the field's semantics; neither structural repacking nor whole-XC copying supplies that evidence.

#### R.4.2 PRMGRP: 11 p00 XCs

Each source below contains a 12-byte `000.prmgrp`: `y740000_p00.xc`, `y900001_p00.xc`, `y901000_p00.xc`, `y901010_p00.xc`, `y901020_p00.xc`, `y901030_p00.xc`, `y901040_p00.xc`, `y901050_p00.xc`, `y901060_p00.xc`, `y901070_p00.xc`, and `y901090_p00.xc`.

No PRMGRP exists in any of the 1,632 supplied B1 XCs. The first u32 resembles a CRC, but its target, remaining fields, runtime use, and appropriate B1 RES category are not established. Some upper 16-bit fields contain values resembling string fragments and cannot simply be presumed zero padding. A strict conversion neither copies this unknown format as if proven compatible nor deletes it or its RES references. The explicit whole-p00 policy is separate.

#### R.4.3 Bone-less models: 89 p00 XCs

All supplied B1 p00s have MBN resources; none of the following 89 YW3 p00s has a same-named B1 counterpart. For the ranges in the table, include every stem in steps of 10, inclusive, and append `_p00.xc`.

| Exact stems or inclusive stem range | Count |
|---|---:|
| y901000, y901010, y901020, y901030, y901040, y901050, y901060, y901070, y901090 | 9 |
| y902000 through y902150 | 16 |
| y903000 through y903150 | 16 |
| y904000 through y904150 | 16 |
| y905000 through y905150 | 16 |
| y906000 through y906150 | 16 |

Of these, 16 use material type 0x0123 and 73 use the already-known 0x0122. Thus bone-less does not imply 0x0123. The six other-slot B1 references (`x511000`, `x521000`, `y287000`, `y461000`, `y477000`, and `y481000` p90) contain only MTN2, MTNINF, CMN, and RES. They are motion archives, not evidence that a bone-less p00 model follows the supported B1 character-model path.

Strict conversion therefore retains its MBN requirement. It does not synthesize a dummy root, import another character's bones, or ignore missing node references. Resolving this limitation requires old-engine evidence for loading such models, or an established rule for the necessary root, bones, and associated RES references. Successful user-reported source-model copying is runtime evidence to investigate separately, not a derived bone-generation rule.

#### R.4.4 RES material 0x0123: 16 p00 XCs

Each of these XCs has one 224-byte material-0x0123 record and no MBN:

| Series | Exact source stems; append `_p00.xc` |
|---|---|
| y901 | y901000, y901010, y901020, y901030, y901040, y901050 |
| y903 | y903010, y903020, y903060, y903070, y903080, y903090, y903100, y903110, y903120, y903130 |

YW3 has 2,264 material-0x0122 records and 16 material-0x0123 records; B1 has 1,138 type-0x0122 records and no type-0x0123 records. Both record layouts are 224 bytes. Ignoring the five name-reference CRC words at 0x00, 0x08, 0x0C, 0x10, and 0x44, the other 51 words of all 16 type-0x0123 records match B1 `x181000_p00.xc` material-0x0122 record 0.

This establishes strong layout similarity, not the tag's runtime meaning. The tag-selection condition, B1 dispatch behavior, and semantics of binding the references through the old category remain unknown. Changing only `CHRC02` to `CHRC01` would leave an unverified category ID; changing only 0x0123 to 0x0122 would assume the categories are interchangeable. Neither follows from equal stride or successful XPCK re-extraction.

There is no correlation with the nonzero PRM tails in R.4.1: all 16 type-0x0123 XCs have normal PRM tails, and all 11 nonzero-tail XCs use 0x0122. No joint PRM/RES rewrite rule can therefore be inferred from these data. The strict path rejects 0x0123 explicitly.

#### R.4.5 XI format 0x04: one p00 XC

`x671000_p00.xc/000.xi` has format 0x04, fields `01 01 10 80 00`, dimensions 256×256, decoded image length 121,600 bytes, 950 observed 128-byte tiles, and maximum tile index 949. Size, decompression, and tile-reference framing are consistent.

Nevertheless, neither a same-named B1 XC nor any format-0x04 example among all 768 supplied B1 XIs exists. Readable framing does not prove that B1 understands the pixel encoding. Strict conversion reports `Unsupported XI image format: 0x04`. Resolution requires evidence that B1 supports this format, or the pixel interpretation and a reliable re-encoding rule to an established format. Deleting or substituting the texture is not a successful conversion.

#### R.4.6 CMN array element type 1: seven UMBRELLA parameters

All seven are 20-byte type-5 arrays with one element and valid RES sizes `(20,8)`. The parameter name is `UMBRELLA` (CRC32 0xD526AC1A), and its sole element uses unverified element type 1. This is distinct from **scalar** CMN value type 1, which is already supported.

| Source p00 XC | Internal CMN |
|---|---|
| y002000_p00.xc | 014.cmn |
| y664020_p00.xc | 015.cmn |
| y664030_p00.xc | 015.cmn |
| y665000_p00.xc | 014.cmn |
| y665010_p00.xc | 014.cmn |
| y665020_p00.xc | 014.cmn |
| y665030_p00.xc | 014.cmn |

No supplied B1 instance establishes this array-element representation. Forcing the element to type 0 would reinterpret its bits as float; forcing it to type 2 would assume CRC-reference semantics. Both discard the actual source type without evidence. The strict validator continues to reject type 1; whole-p00 copy intentionally preserves it instead of claiming its meaning is known.

#### R.4.7 COLLISION_RECT scalar/RES size disagreement: one p00 XC

YW3 `x024000_p00.xc/003.cmn` is a 12-byte scalar named `COLLISION_RECT` (CRC32 0x1D52218A), with main value type 0 and value bits zero. Its RES 0x00C8 entry stores `(total_size, extra_size)=(12,0)`, whereas all supplied B1 12-byte scalar entries use `(0,0)` under the established rule. No B1 instance of `COLLISION_RECT` was supplied.

The internal scalar alone is readable; strict p00 fails at the **cross-file RES size check**. Changing the record to `(0,0)` is not a proven downgrade and may alter an unknown parameter's loading semantics. This exception remains unresolved rather than being normalized silently.

The two unresolved special motion cases are separate from these model topics: `x611000_p80.xc/000.mtninf2` (A=4, event 0x044E, auxiliary value 0) and `x791000_p84.xc/000.mtninf2` (A=16). Appendix M and C.4 state their evidence and unchanged failure policy; whole-p00 preservation does not bypass motion conversion.

### R.5 Native B1 LKAT exception and a weakened field interpretation

The native B1 p00 regression accepted 546 of 547 supplied model archives through the model pipeline. Its one known unsupported native case is `y275010_p00.xc/000.lkat`. This is a coverage limitation of the current parser, not a YW3 conversion failure and not proof that the B1 original is corrupt. No same-named YW3 p00 was supplied.

Its 152-byte file still fits a 0x28-byte header followed by four 0x1C-byte records. Compared with B1 `y275000_p00.xc/000.lkat`, the only differences are byte 0x25 (`00 → CC`) and byte 0x26 (`00 → 4C`). Header bytes 0x00–0x23 and all four records are otherwise identical.

| B1 source | Bytes 0x24..0x27 | u16@0x24 | Low byte @0x24 | Actual records |
|---|---|---:|---:|---:|
| y275000 | `04 00 00 3F` | 4 | 4 | 4 |
| y275010 | `04 CC 4C 3F` | 52,228 | 4 | 4 |

The established u16-count validator rejects the latter. Its upper three bytes `CC 4C 3F` equal the upper three bytes of float32 0.8 (`CD CC 4C 3F`); the normal counterpart similarly retains the upper three bytes of float32 0.5. A low-eight-bit count packed with a float-like upper-24-bit parameter is therefore plausible. It is an inference from one native exception, not a confirmed decoder rule, and is not implemented by automatically changing the count width.

This observation weakens the initial interpretation of u16@0x26 as a simple generation-compatibility field. The existing normalization to 0x3F00 is retained as the established conversion policy supported by the original ten official pairs and their reported game tests, while the exact runtime meaning remains unknown. Do not equate “an established tested policy” with “every header field's semantics have been identified.”

Across all 6,492 supplied YW3 XCs, 1,038 LKAT files exist, including 1,021 in p00. Every one has byte 0x25 zero and a u16 count agreeing with `0x28+0x1C*N`; none has this exceptional packed pattern. B1 has 532 LKAT files across all 1,632 XCs; only this one has a nonzero byte 0x25. Permitting it is not required to process the supplied YW3 corpus. Future same-form source inputs require additional packed-field analysis, not a silent relaxation or a corruption assumption.

### R.6 Verification guarantees and what remains to be collected

The model recovery regression suite checks all the listed YW3/B1 ATR/MTR/MBN files, every supplied B1 PRM, the three source legacy PRMs, specific variable-length and flag evidence, preservation of YW3 bytes, and continued rejection of unknown nonzero PRM tails. Malformed compressed headers, invalid raw sizes, truncated streams, duplicate LUT offsets, unknown MBN flags, invalid legacy markers, and invalid name bounds remain rejection cases.

The model and XI audit artifacts were private development evidence, not release dependencies. Their relevant counts, source names, header rules, formulas, limits, and unsupported cases have been incorporated above. Reproducing a corpus-wide comparison requires lawfully obtained source data; no proprietary assets or supplemental audit files are needed to read this public reference.

Three conclusions must remain separate:

1. **Shared-format validation:** a known internal resource passed structural and local-reference checks and was retained byte-for-byte.
2. **Strict XC conversion:** all selected internals and references passed the supported conversion path, and the repacked XPCK re-extracted to the intended dictionary.
3. **Runtime behavior:** B1 actually displayed the model and texture and used its bones, attachments, materials, parameters, and converted motions as intended.

Whole-p00 preservation adds a different conclusion: the original XPCK passed container validation and its complete XC bytes were copied exactly. It does not establish conclusions 1 or 2 for unknown internals, and none of these structural conclusions by itself establishes conclusion 3. Additional game observations, same-purpose old-format examples, or loader evidence are still needed for the unresolved semantics documented here.
