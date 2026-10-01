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

In short, character XC archives reuse the same XPCK foundation as effect XC archives, but their internal formats are character-specific. `mtn3`, `mtninf2`, `prm`, `lkat`, and `RES.bin` require explicit generation conversion. `atr`, `mtr`, `mbn`, `sil`, `xi`, `txp`, and `cmn` should preserve the YW3 asset content after strict validation of known structure.

## 2. Evidence and Confidence Levels

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
| `0x26` | 2 | Generation compatibility value |
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

Every YWB1 file uses `0x3F00`. Replacing only these two bytes produces an exact official match for all ten pairs.

Seven files have four records; three files have two records.

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

Two fixed ATR layouts were observed.

| Offset | Size | Description |
|---:|---:|---|
| `0x00` | 8 | `ATRC01\0\0` |
| `0x08` | 4 | Header length `0x0C` |
| `0x0C` | 2 | Layout identifier |

| Identifier | Total length | YW3 count |
|---:|---:|---:|
| `0x01E3` | 40 | 10 |
| `0x01E4` | 36 | 9 |

The complete bit layout after `0x0E` is unknown. Filenames and RES placement suggest material attribute data.

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

Nonzero LUTC offsets are packed from the first slot, unique, ascending, and four-byte aligned.

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

XI stores model textures. Its magic is `IMGC00`; the observed image format is ETC1.

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
| `0x38` | 4 | Duplicate of `T` |
| `0x3C` | 4 | Compressed image-data size `I` |
| `0x40` | 8 | Zero |

### 16.3 Data Region

```text
0x48                         T bytes of Huffman4-compressed tile table
align4(0x48 + T)             I bytes of LZ10-compressed ETC1 image data
align4(image_start + I)      EOF
```

Expanded tile-table size is:

```text
tile_table_raw_size = width * height / 32
```

Expanded image length is in 32-byte units and no greater than `width * height / 2`. The data appears sparse: the tile table maps used tiles to image data rather than storing a fixed-size block for every pixel.

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

The final two fields are zero for a 12-byte scalar.

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

- A new ATR layout identifier.
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

The p00/p80/p84 set generated under this policy works correctly in both the emulator and on real hardware.
