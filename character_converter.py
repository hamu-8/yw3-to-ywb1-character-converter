#!/usr/bin/env python3
"""YW3 character-resource converters.

Implemented standalone conversions:

* ``mtn3`` -> ``mtn2``
* bundled ``mtn3``/``mtm3``/``imm3`` -> individual v2 animations
* ``mtninf2`` -> individual ``mtninf`` files
* ordinary ``mtminf2``/``imminf2`` -> individual v1 INF files
* validated byte-preserving existing v2-animation/v1-INF copies
* character ``prm`` -> YWB1-compatible ``prm``
* character ``lkat`` -> YWB1-compatible ``lkat``
* validated, byte-identical character ``sil`` copy
* validated, byte-identical ``atr``/``mtr``/``mbn``/``xi``/``txp``/``cmn`` copies
* extracted p00 model contents -> converted model contents
* extracted p80/p84 motion contents -> converted motion contents
* one-character p00/p80/p84 XC trio -> three converted XC archives

The effect converter is intentionally not imported so the two tools can
evolve independently.
"""

from __future__ import annotations

import argparse
import binascii
from collections import deque
import math
import os
import shutil
import struct
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class ConversionError(Exception):
    """Raised when an input does not match a supported binary layout."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConversionError(message)


def u32(data: bytes, offset: int) -> int:
    require(offset >= 0 and offset + 4 <= len(data), f"u32 offset is out of range: 0x{offset:X}")
    return struct.unpack_from("<I", data, offset)[0]


def u16(data: bytes, offset: int) -> int:
    require(offset >= 0 and offset + 2 <= len(data), f"u16 offset is out of range: 0x{offset:X}")
    return struct.unpack_from("<H", data, offset)[0]


def p32(value: int) -> bytes:
    return struct.pack("<I", value)


def p16(value: int) -> bytes:
    return struct.pack("<H", value)


def crc32(raw: bytes) -> int:
    return binascii.crc32(raw) & 0xFFFFFFFF


def level5_decompress(data: bytes) -> bytes:
    """Decompress the Level-5 kinds needed by character resources.

    Supported kinds are uncompressed (0), LZ10 (1), Huffman4 (2),
    Huffman8 (3), and RLE (4).
    Character MTN uses kind 3, while two source XPCK archives use kind 2 for
    their compressed RES.bin.
    """

    require(len(data) >= 4, "Level-5 compressed data is shorter than 4 bytes")
    header = u32(data, 0)
    kind = header & 7
    output_size = header >> 3

    if kind == 0:
        require(output_size <= len(data) - 4, "Uncompressed Level-5 block ends prematurely")
        return data[4 : 4 + output_size]

    if kind == 1:
        source = 4
        output = bytearray()
        while len(output) < output_size:
            require(source < len(data), "LZ10 flag stream ends prematurely")
            flags = data[source]
            source += 1
            for bit in range(7, -1, -1):
                if len(output) >= output_size:
                    break
                if flags & (1 << bit):
                    require(source + 2 <= len(data), "LZ10 back-reference ends prematurely")
                    first, second = data[source], data[source + 1]
                    source += 2
                    length = (first >> 4) + 3
                    distance = (((first & 0x0F) << 8) | second) + 1
                    require(distance <= len(output), "LZ10 back-reference distance exceeds the decoded output")
                    for _ in range(length):
                        if len(output) >= output_size:
                            break
                        output.append(output[-distance])
                else:
                    require(source < len(data), "LZ10 literal stream ends prematurely")
                    output.append(data[source])
                    source += 1
        return bytes(output)

    if kind in {2, 3}:
        label = "Huffman4" if kind == 2 else "Huffman8"
        require(len(data) >= 6, f"{label} header is too short")
        tree_size = data[4]
        root = data[5]
        tree_end = 6 + tree_size * 2
        require(tree_end <= len(data), f"{label} tree region ends prematurely")
        tree = data[6:tree_end]
        source = tree_end
        symbols = bytearray()
        symbol_count = output_size * 2 if kind == 2 else output_size
        bit_index = 0
        code = 0
        node = root
        next_pair = 0

        while len(symbols) < symbol_count:
            if bit_index % 32 == 0:
                require(source + 4 <= len(data), f"{label} bitstream ends prematurely")
                code = u32(data, source)
                source += 4

            bit = (code >> (31 - (bit_index % 32))) & 1
            direction = 2 if bit == 0 else 1
            next_pair += ((node & 0x3F) << 1) + 2
            child_index = next_pair - direction
            require(0 <= child_index < len(tree), f"{label} tree reference is out of range")
            is_leaf = ((node >> (5 + direction)) & 1) != 0
            node = tree[child_index]
            if is_leaf:
                symbols.append(node)
                node = root
                next_pair = 0
            bit_index += 1

        if kind == 3:
            return bytes(symbols)
        require(all(symbol <= 0x0F for symbol in symbols), "Huffman4 leaf contains a value wider than 4 bits")
        return bytes(
            symbols[index] | (symbols[index + 1] << 4)
            for index in range(0, len(symbols), 2)
        )

    if kind == 4:
        source = 4
        output = bytearray()
        while len(output) < output_size:
            require(source < len(data), "RLE control stream ends prematurely")
            control = data[source]
            source += 1
            if control & 0x80:
                require(source < len(data), "RLE run value is missing")
                length = (control & 0x7F) + 3
                output.extend([data[source]] * length)
                source += 1
            else:
                length = control + 1
                require(source + length <= len(data), "RLE literal stream ends prematurely")
                output.extend(data[source : source + length])
                source += length
        del output[output_size:]
        return bytes(output)

    raise ConversionError(f"Unsupported Level-5 compression type: {kind}")


def level5_lz10_compress(data: bytes) -> bytes:
    """Encode a byte string as a Level-5 kind-1/LZ10 block."""

    require(len(data) < (1 << 29), "LZ10 input exceeds the 29-bit size limit")
    output = bytearray(p32((len(data) << 3) | 1))
    # Positions sharing the same first three bytes are enough to find every
    # possible LZ10 match.  Keeping a bounded recent chain avoids the original
    # O(input_size * 0x1000) scan on large character animations while still
    # producing a valid greedy stream.
    candidates_by_prefix: dict[bytes, deque[int]] = {}
    next_insert = 0

    def index_until(end: int) -> None:
        nonlocal next_insert
        while next_insert < end:
            if next_insert + 3 <= len(data):
                key = data[next_insert : next_insert + 3]
                candidates = candidates_by_prefix.setdefault(key, deque())
                candidates.append(next_insert)
                oldest = next_insert - 0x1000
                while candidates and candidates[0] < oldest:
                    candidates.popleft()
            next_insert += 1

    position = 0
    while position < len(data):
        flag_position = len(output)
        output.append(0)
        flags = 0
        for bit in range(7, -1, -1):
            if position >= len(data):
                break
            index_until(position)
            best_length = 0
            best_distance = 0
            key = data[position : position + 3]
            candidates = candidates_by_prefix.get(key, ())
            # The stream need not use an optimal parse.  Trying the 64 nearest
            # same-prefix positions gives predictable speed and good output
            # size for the observed MTN/MINF data.
            for checked, candidate in enumerate(reversed(candidates)):
                if checked == 64:
                    break
                if position - candidate > 0x1000:
                    break
                length = 3
                while (
                    length < 18
                    and position + length < len(data)
                    and data[candidate + length] == data[position + length]
                ):
                    length += 1
                if length > best_length:
                    best_length = length
                    best_distance = position - candidate
                if best_length == 18:
                    break
            if best_length >= 3:
                flags |= 1 << bit
                value = ((best_length - 3) << 12) | (best_distance - 1)
                output.extend((value >> 8, value & 0xFF))
                position += best_length
            else:
                output.append(data[position])
                position += 1
        output[flag_position] = flags
    return bytes(output)


def level5_lz10_compress_canonical(data: bytes) -> bytes:
    """Encode LZ10 using the match choices observed in official XPCK files.

    Candidates are visited from farthest to nearest and an equal-length match
    does not replace the current choice.  XPCK only applies this encoder to its
    small filename table and RES.bin, so the exhaustive search is acceptable.
    """

    require(len(data) < (1 << 29), "LZ10 input exceeds the 29-bit size limit")
    output = bytearray(p32((len(data) << 3) | 1))
    position = 0
    while position < len(data):
        flag_position = len(output)
        output.append(0)
        flags = 0
        for bit in range(7, -1, -1):
            if position >= len(data):
                break
            best_length = 0
            best_distance = 0
            window_start = max(0, position - 0x1000)
            for candidate in range(window_start, position):
                if data[candidate] != data[position]:
                    continue
                length = 1
                while (
                    length < 18
                    and position + length < len(data)
                    and data[candidate + length] == data[position + length]
                ):
                    length += 1
                if length > best_length:
                    best_length = length
                    best_distance = position - candidate
                if best_length == 18:
                    break
            if best_length >= 3:
                flags |= 1 << bit
                value = ((best_length - 3) << 12) | (best_distance - 1)
                output.extend((value >> 8, value & 0xFF))
                position += best_length
            else:
                output.append(data[position])
                position += 1
        output[flag_position] = flags
    return bytes(output)


PRM_OUTER_HEADER_SIZE = 0x40
PRM_YW3_COMPATIBILITY_SIZE = 0x4C
PRM_YWB1_COMPATIBILITY_SIZE = 0x44
PRM_COMPATIBILITY_REPLACEMENT = b"\0\0\0\0\x01\x01\0\0"
PRM_SHIFTED_OFFSET_FIELDS = (0x10, 0x18, 0x20, 0x28, 0x30, 0x38)


def convert_character_prm(data: bytes) -> bytes:
    """Downgrade one YW3 character PRM without rewriting vertex data.

    The character layout identifies the generation-specific block with the
    outer-header offsets at 0x0C and 0x10.  YW3 ends that 0x4C-byte block in
    sixteen zero bytes, while YWB1 replaces those bytes with an eight-byte
    compatibility marker.  A small number of YW3 archives already contain
    the verified 0x44-byte legacy block; preserve those PRMs after checking
    their marker and name ranges.  XPVB/XPVI and their compressed payloads
    are kept byte-for-byte so no normal or skin-weight rounding is introduced.
    """

    require(len(data) >= PRM_OUTER_HEADER_SIZE, "PRM header is too short")
    require(data[:4] == b"XMPR", "PRM magic is not XMPR")
    require(
        u32(data, 0x04) == PRM_OUTER_HEADER_SIZE,
        f"PRM outer-header size is not 0x{PRM_OUTER_HEADER_SIZE:X}",
    )
    require(data[0x40:0x44] == b"XPRM", "PRM inner magic is not XPRM")

    compatibility_start = u32(data, 0x0C)
    compatibility_end = u32(data, 0x10)
    require(
        PRM_OUTER_HEADER_SIZE <= compatibility_start <= compatibility_end <= len(data),
        "PRM generation-difference block range is invalid",
    )
    compatibility_size = compatibility_end - compatibility_start
    if compatibility_size == PRM_YWB1_COMPATIBILITY_SIZE:
        require(
            data[compatibility_end - 8 : compatibility_end]
            == PRM_COMPATIBILITY_REPLACEMENT,
            "Legacy PRM compatibility marker is unsupported",
        )
        name_offset = u32(data, 0x30)
        material_offset = u32(data, 0x38)
        require(
            compatibility_end <= name_offset <= material_offset <= len(data),
            "Legacy PRM name or material-name range is invalid",
        )
        require(
            name_offset + u32(data, 0x34) <= material_offset,
            "Legacy PRM name length exceeds its region",
        )
        require(
            material_offset + u32(data, 0x3C) <= len(data),
            "Legacy PRM material-name length exceeds the file",
        )
        return data
    require(
        compatibility_size == PRM_YW3_COMPATIBILITY_SIZE,
        "PRM generation-difference block size is not the YW3 value 0x4C "
        f"(found: 0x{compatibility_size:X}); the PRM may already be converted",
    )

    replacement_start = compatibility_end - 16
    require(
        replacement_start >= compatibility_start,
        "Cannot read the final 16 bytes of the PRM generation-difference block",
    )
    require(
        data[replacement_start:compatibility_end] == bytes(16),
        "The final 16 bytes of the PRM generation-difference block are not zero-filled",
    )

    removed_size = 16 - len(PRM_COMPATIBILITY_REPLACEMENT)
    output = bytearray(
        data[:replacement_start]
        + PRM_COMPATIBILITY_REPLACEMENT
        + data[compatibility_end:]
    )

    for offset_field in PRM_SHIFTED_OFFSET_FIELDS:
        value = u32(data, offset_field)
        if value >= compatibility_end:
            struct.pack_into("<I", output, offset_field, value - removed_size)

    require(
        u32(output, 0x10) - u32(output, 0x0C) == PRM_YWB1_COMPATIBILITY_SIZE,
        "Internal error: could not convert the PRM generation-difference block to 0x44 bytes",
    )
    require(
        len(output) == len(data) - removed_size,
        "Internal error: converted PRM size did not decrease by 8 bytes",
    )
    return bytes(output)


LKAT_HEADER_SIZE = 0x28
LKAT_RECORD_SIZE = 0x1C
LKAT_RECORD_COUNT_OFFSET = 0x24
LKAT_COMPATIBILITY_OFFSET = 0x26
LKAT_YWB1_COMPATIBILITY_VALUE = 0x3F00


def convert_character_lkat(data: bytes) -> bytes:
    """Set the character LKAT compatibility field to the YWB1 value."""

    require(len(data) >= LKAT_HEADER_SIZE, "LKAT header is too short")
    record_count = u16(data, LKAT_RECORD_COUNT_OFFSET)
    expected_size = LKAT_HEADER_SIZE + LKAT_RECORD_SIZE * record_count
    require(
        len(data) == expected_size,
        "LKAT size does not match the header record count "
        f"(expected: {expected_size}, actual: {len(data)})",
    )

    output = bytearray(data)
    struct.pack_into(
        "<H",
        output,
        LKAT_COMPATIBILITY_OFFSET,
        LKAT_YWB1_COMPATIBILITY_VALUE,
    )
    return bytes(output)


SIL_HEADER_SIZE = 0x20
SIL_SECTION_DESCRIPTORS = ((0x10, 0x14), (0x18, 0x1C))


def convert_character_sil(data: bytes) -> bytes:
    """Validate one character SIL and return a byte-identical copy."""

    require(len(data) >= SIL_HEADER_SIZE, "SIL header is too short")
    require(data[:4] == b"XCSL", "SIL magic is not XCSL")
    require(
        u32(data, 0x04) == SIL_HEADER_SIZE,
        f"SIL header size is not 0x{SIL_HEADER_SIZE:X}",
    )

    sections: list[tuple[int, int]] = []
    for index, (offset_field, size_field) in enumerate(SIL_SECTION_DESCRIPTORS):
        section_offset = u32(data, offset_field)
        section_size = u32(data, size_field)
        require(
            section_offset >= SIL_HEADER_SIZE and section_size >= 4,
            f"SIL CMBC section {index} has an invalid offset or size",
        )
        section_end = section_offset + section_size
        require(
            section_end <= len(data),
            f"SIL CMBC section {index} is outside the file",
        )
        require(
            data[section_offset : section_offset + 4] == b"CMBC",
            f"SIL section {index} magic is not CMBC",
        )
        sections.append((section_offset, section_end))

    require(
        sections[0][1] == sections[1][0],
        "The two SIL CMBC sections are not contiguous",
    )
    require(
        sections[1][1] == len(data),
        "The end of the second SIL CMBC section does not match the end of the file",
    )
    return data


ATR_MAGIC = b"ATRC01\0\0"
ATR_HEADER_SIZE = 0x0C
# These values are Level-5 headers, not layout IDs: (0x3C << 3) | kind.
# Keep the historical constant for callers that imported it, but do not use
# its old fixed compressed-file lengths as a structural constraint.
ATR_LAYOUT_SIZES = {0x01E3: 40, 0x01E4: 36}
ATR_RAW_SIZE = 0x3C


def convert_character_atr(data: bytes) -> bytes:
    """Validate the variable-length compressed ATR and copy it unchanged."""

    require(len(data) >= 0x10, "ATR header is too short")
    require(data[:8] == ATR_MAGIC, "ATR magic is not ATRC01")
    require(
        u32(data, 0x08) == ATR_HEADER_SIZE,
        f"ATR header size is not 0x{ATR_HEADER_SIZE:X}",
    )
    compressed = data[ATR_HEADER_SIZE:]
    require(
        u32(compressed, 0) & 7 in {3, 4},
        "ATR payload is not Huffman8/RLE-compressed",
    )
    require(u32(compressed, 0) >> 3 == ATR_RAW_SIZE, "ATR declared raw size is not 0x3C")
    require(len(data) % 4 == 0, "ATR size is not 4-byte aligned")
    raw = level5_decompress(compressed)
    require(len(raw) == ATR_RAW_SIZE, "Decompressed ATR size is not 0x3C")
    require(u32(raw, 0) == ATR_RAW_SIZE, "ATR inner-header size is not 0x3C")
    return data


MTR_MAGIC = b"MTRC00\0\0"
MTR_HEADER_SIZE = 0x18
MTR_METADATA_SIZE = 0xE8
LUTC_MAGIC = b"LUTC00\0\0"
LUTC_RAW_SIZE = 0x800


def convert_character_mtr(data: bytes) -> bytes:
    """Validate one character MTR/LUTC container and copy it unchanged."""

    require(len(data) >= MTR_HEADER_SIZE + 4, "MTR header or compressed region is too short")
    require(data[:8] == MTR_MAGIC, "MTR magic is not MTRC00")
    require(
        u16(data, 0x08) == MTR_HEADER_SIZE,
        f"MTR header size is not 0x{MTR_HEADER_SIZE:X}",
    )
    require(data[0x0C:0x10] == bytes(4), "MTR reserved region at 0x0C is not zero-filled")
    require(data[0x14:0x18] == bytes(4), "MTR reserved region at 0x14 is not zero-filled")
    require(len(data) % 4 == 0, "MTR size is not 4-byte aligned")

    raw_offsets = (u16(data, 0x0A), u16(data, 0x10), u16(data, 0x12))
    nonzero_offsets = [offset for offset in raw_offsets if offset]
    # The three fields identify independent LUT slots, not a packed list.
    # B1 y133800/y191000/y191010 use (0, 92, 2128); an absent first LUT
    # therefore does not make the later two invalid.  Preserve slot identity.
    require(
        nonzero_offsets == sorted(set(nonzero_offsets)),
        "MTR LUTC offsets are not in ascending order or contain duplicates",
    )
    for offset in nonzero_offsets:
        require(
            offset >= MTR_HEADER_SIZE + 4 and offset < len(data) and offset % 4 == 0,
            f"Invalid MTR LUTC offset: 0x{offset:X}",
        )

    metadata_end = nonzero_offsets[0] if nonzero_offsets else len(data)
    metadata = data[MTR_HEADER_SIZE:metadata_end]
    require(u32(metadata, 0) & 7 == 1, "MTR metadata is not LZ10-compressed")
    require(
        len(level5_decompress(metadata)) == MTR_METADATA_SIZE,
        f"Decompressed MTR metadata size is not 0x{MTR_METADATA_SIZE:X}",
    )

    for index, start in enumerate(nonzero_offsets):
        end = nonzero_offsets[index + 1] if index + 1 < len(nonzero_offsets) else len(data)
        block = data[start:end]
        require(len(block) >= 20, f"MTR LUTC block {index} is too short")
        require(block[:8] == LUTC_MAGIC, f"MTR LUTC block {index} has invalid magic")
        require(
            u32(block, 0x08) == 0x00100000 and u32(block, 0x0C) == 0,
            f"MTR LUTC block {index} has an unsupported header",
        )
        compressed = block[0x10:]
        require(
            u32(compressed, 0) & 7 in {2, 4},
            f"MTR LUTC block {index} is not Huffman4/RLE-compressed",
        )
        require(
            len(level5_decompress(compressed)) == LUTC_RAW_SIZE,
            f"Decompressed MTR LUTC block {index} size is not 0x{LUTC_RAW_SIZE:X}",
        )
    return data


MBN_SIZE = 0xA8
MBN_FLOAT_COUNT = 39
MBN_VERIFIED_FLAGS = {4, 5, 12}


def convert_character_mbn(data: bytes) -> bytes:
    """Validate one character bone/node MBN and copy it unchanged."""

    require(len(data) == MBN_SIZE, f"MBN size is not 0x{MBN_SIZE:X}")
    require(u32(data, 0x00) != 0, "MBN node-ID CRC32 is zero")
    require(
        u32(data, 0x08) in MBN_VERIFIED_FLAGS,
        "MBN flags are not one of the verified values 4, 5, or 12",
    )
    values = struct.unpack_from(f"<{MBN_FLOAT_COUNT}f", data, 0x0C)
    require(all(math.isfinite(value) for value in values), "MBN contains a non-finite float value")
    return data


XI_MAGIC = b"IMGC00\0\0"
XI_DATA_OFFSET = 0x48
XI_FORMAT_ETC1 = 0x1B
# Each tuple is (header bytes at 0x0B..0x0F, stored bytes per 8x8 tile).
# Both layouts occur in native YWB1 character XC archives. Other image formats
# remain unsupported even if their storage can be decoded structurally.
XI_VERIFIED_FORMATS = {
    XI_FORMAT_ETC1: (bytes.fromhex("01 01 04 20 00"), 32),
    0x1C: (bytes.fromhex("01 01 08 40 00"), 64),
}
XI_COMPRESSION_KINDS = {0, 1, 2, 3, 4}


def convert_character_xi(data: bytes) -> bytes:
    """Validate one native-compatible character XI image and copy unchanged.

    Offset 0x34 stores the encoded tile-table length, while 0x38 stores its
    four-byte-aligned region length (not necessarily an exact duplicate).
    The tile table contains one u16 index per 8x8 tile. Its references must
    cover exactly the contiguous tile blocks stored in the decoded image.
    """

    require(len(data) >= XI_DATA_OFFSET + 8, "XI header or image region is too short")
    require(data[:8] == XI_MAGIC, "XI magic is not IMGC00")
    require(u16(data, 0x08) == 0x30, "XI inner-header size is not 0x30")
    image_format = data[0x0A]
    require(image_format in XI_VERIFIED_FORMATS, f"Unsupported XI image format: 0x{image_format:02X}")
    format_fields, tile_bytes = XI_VERIFIED_FORMATS[image_format]
    require(data[0x0B:0x10] == format_fields, "XI format fields do not match the verified image format")
    width, height = struct.unpack_from("<2H", data, 0x10)
    require(
        width > 0 and height > 0 and width % 8 == 0 and height % 8 == 0,
        f"Invalid XI image dimensions: {width}x{height}",
    )
    require(
        u32(data, 0x14) == 0x30
        and u32(data, 0x18) == 0x00010030
        and u32(data, 0x1C) == XI_DATA_OFFSET
        and u32(data, 0x20) == 3,
        "XI fixed header fields are unsupported",
    )
    require(data[0x24:0x34] == bytes(0x10), "XI reserved region at 0x24 is not zero-filled")
    require(data[0x40:0x48] == bytes(8), "XI reserved region at 0x40 is not zero-filled")

    tile_size = u32(data, 0x34)
    require(
        tile_size > 4 and u32(data, 0x38) == ((tile_size + 3) & ~3),
        "XI aligned tile-table size is invalid",
    )
    image_size = u32(data, 0x3C)
    require(image_size > 4, "XI image-data size is invalid")
    tile_start = XI_DATA_OFFSET
    tile_end = tile_start + tile_size
    image_start = (tile_end + 3) & ~3
    image_end = image_start + image_size
    expected_size = (image_end + 3) & ~3
    require(expected_size == len(data), "XI compressed-region sizes do not match the file size")
    require(data[tile_end:image_start] == bytes(image_start - tile_end), "Padding after the XI tile table is not zero-filled")
    require(data[image_end:] == bytes(len(data) - image_end), "XI trailing padding is not zero-filled")

    tile_data = data[tile_start:tile_end]
    require(u32(tile_data, 0) & 7 in XI_COMPRESSION_KINDS, "XI tile table has an unsupported compression kind")
    raw_tiles = level5_decompress(tile_data)
    require(
        len(raw_tiles) == width * height // 32,
        "Decompressed XI tile-table size does not match the image dimensions",
    )

    image_data = data[image_start:image_end]
    require(u32(image_data, 0) & 7 in XI_COMPRESSION_KINDS, "XI image data has an unsupported compression kind")
    raw_image = level5_decompress(image_data)
    require(
        raw_image and len(raw_image) % tile_bytes == 0
        and len(raw_image) <= width * height // 64 * tile_bytes,
        "Decompressed XI image-data size does not match the verified tile format",
    )
    stored_tiles = len(raw_image) // tile_bytes
    indices = struct.unpack(f"<{len(raw_tiles) // 2}H", raw_tiles)
    require(
        set(indices) == set(range(stored_tiles)),
        "XI tile-table references do not cover exactly the stored image tiles",
    )
    return data


TXP_SIZE = 0x24


def convert_character_txp(data: bytes) -> bytes:
    """Validate one character texture-projection TXP and copy it unchanged."""

    require(len(data) == TXP_SIZE, f"TXP size is not 0x{TXP_SIZE:X}")
    require(u32(data, 0x00) != 0, "TXP projection-name CRC32 is zero")
    require(u32(data, 0x04) != 0, "TXP material-name CRC32 is zero")
    values = struct.unpack_from("<7f", data, 0x08)
    require(all(math.isfinite(value) for value in values), "TXP contains a non-finite float value")
    return data


CMN_SCALAR_TYPES = {0, 1}
CMN_ARRAY_TYPE = 5
CMN_ARRAY_ELEMENT_TYPES = {0, 2}


def convert_character_cmn(data: bytes) -> bytes:
    """Validate one named character parameter CMN and copy it unchanged."""

    require(len(data) >= 12, "CMN is shorter than 12 bytes")
    require(u32(data, 0x04) != 0, "CMN parameter-name CRC32 is zero")
    value_type = u16(data, 0x08)
    element_count = u16(data, 0x0A)
    if value_type in CMN_SCALAR_TYPES:
        require(element_count == 0, "CMN scalar element count is not zero")
        require(len(data) == 12, "CMN scalar size is not 12 bytes")
        if value_type == 0:
            require(math.isfinite(struct.unpack_from("<f", data, 0)[0]), "CMN contains a non-finite float value")
        return data

    require(value_type == CMN_ARRAY_TYPE, f"Unsupported CMN value type: {value_type}")
    require(u32(data, 0x00) == 0, "First value of CMN array is not zero")
    require(element_count > 0, "CMN array element count is zero")
    require(
        len(data) == 12 + element_count * 8,
        "CMN array size does not match the element count",
    )
    for index in range(element_count):
        offset = 12 + index * 8
        element_type = u32(data, offset + 4)
        require(
            element_type in CMN_ARRAY_ELEMENT_TYPES,
            f"CMN array element {index} has an unsupported type: {element_type}",
        )
        if element_type == 0:
            require(
                math.isfinite(struct.unpack_from("<f", data, offset)[0]),
                f"CMN array element {index} contains a non-finite float value",
            )
        else:
            require(u32(data, offset) != 0, f"CMN array element {index} has a zero CRC32")
    return data


@dataclass(frozen=True)
class XpckEntry:
    name: bytes
    name_crc: int
    name_offset: int
    data_offset: int
    data: bytes


def unpack_xpck_archive(archive: bytes) -> dict[str, bytes]:
    """Validate and unpack one flat XPCK archive; RES.bin is decompressed."""

    require(len(archive) >= 20, "XPCK header is too short")
    require(archive[:4] == b"XPCK", "XPCK magic does not match")
    (
        packed_count,
        info_offset4,
        name_offset4,
        data_offset4,
        info_size4,
        name_size4,
        data_size4,
    ) = struct.unpack_from("<6HI", archive, 4)

    file_count = packed_count & 0x0FFF
    index_bits = packed_count >> 12
    require(1 <= file_count <= 0x0FFF, "XPCK file count is invalid")
    require(
        index_bits == (file_count - 1).bit_length(),
        "XPCK file-count bit width is invalid",
    )

    info_offset = info_offset4 * 4
    name_offset = name_offset4 * 4
    data_offset = data_offset4 * 4
    info_size = info_size4 * 4
    name_size = name_size4 * 4
    data_size = data_size4 * 4
    require(info_size == file_count * 12, "XPCK info-table size does not match the file count")
    require(20 <= info_offset <= name_offset <= data_offset, "XPCK table offsets are in an invalid order")
    require(info_offset + info_size <= name_offset, "XPCK info table overlaps the name table")
    require(name_offset + name_size <= data_offset, "XPCK name table overlaps the data region")
    require(data_offset + data_size == len(archive), "XPCK data-region size does not match the archive size")

    raw_names = level5_decompress(archive[name_offset : name_offset + name_size])
    extracted: dict[str, bytes] = {}
    seen_raw_names: set[bytes] = set()
    previous_crc = -1
    intervals: list[tuple[int, int, str]] = []

    for index in range(file_count):
        record_offset = info_offset + index * 12
        name_crc, raw_name_offset, offset_low, size_low, offset_high, size_high = (
            struct.unpack_from("<IHHHBB", archive, record_offset)
        )
        require(
            name_crc > previous_crc,
            "XPCK info table is not sorted by CRC32 or contains duplicate CRC32 values",
        )
        previous_crc = name_crc
        require(raw_name_offset < len(raw_names), "XPCK filename offset is out of range")
        name_end = raw_names.find(b"\0", raw_name_offset)
        require(name_end >= raw_name_offset, "XPCK filename is not NUL-terminated")
        raw_name = raw_names[raw_name_offset:name_end]
        require(raw_name, "XPCK contains an empty filename")
        require(raw_name not in seen_raw_names, "XPCK contains duplicate filenames")
        require(crc32(raw_name) == name_crc, "XPCK filename CRC32 does not match")
        seen_raw_names.add(raw_name)

        try:
            name = raw_name.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ConversionError("XPCK filename is not valid UTF-8") from error
        require(
            name not in {".", ".."}
            and "/" not in name
            and "\\" not in name
            and ":" not in name,
            f"XPCK contains an unsafe filename: {name!r}",
        )

        relative_offset = ((offset_high << 16) | offset_low) * 4
        size = (size_high << 16) | size_low
        require(relative_offset + size <= data_size, f"XPCK data is out of range: {name}")
        start = data_offset + relative_offset
        payload = archive[start : start + size]
        intervals.append((relative_offset, relative_offset + size, name))
        if name == "RES.bin":
            payload = level5_decompress(payload)
            require(
                payload[:6] in {b"CHRC00", b"CHRC01", b"CHRC02"},
                "Decompressed RES.bin magic inside XPCK is invalid",
            )
        extracted[name] = payload

    intervals.sort()
    require(intervals[0][0] == 0, "XPCK data region begins with unreferenced data")
    for index, (start, end, name) in enumerate(intervals):
        next_start = intervals[index + 1][0] if index + 1 < len(intervals) else data_size
        require(end <= next_start, f"XPCK file data overlaps: {name}")
        padding_size = 4 - ((end - start) % 4)
        require(next_start - end == padding_size, f"XPCK padding length is invalid: {name}")
        padding = archive[data_offset + end : data_offset + next_start]
        require(padding == bytes(padding_size), f"XPCK padding is not zero-filled: {name}")

    require("RES.bin" in extracted, "XPCK does not contain RES.bin")
    return extracted


def pack_xpck_files(files: dict[str, bytes]) -> bytes:
    """Build one deterministic XPCK archive from a flat in-memory file set."""

    require(files, "There are no files to store in XPCK")
    require(len(files) <= 0x0FFF, "XPCK file count exceeds 4095")
    remaining_yw3 = sorted(
        name
        for name in files
        if Path(name).suffix.lower()
        in {".mtn3", ".mtm3", ".imm3", ".mtninf2", ".mtminf2", ".imminf2"}
    )
    require(
        not remaining_yw3,
        "Unconverted YW3 formats remain: " + ", ".join(remaining_yw3),
    )

    names: list[bytes] = []
    name_offsets: dict[bytes, int] = {}
    seen_crcs: dict[int, bytes] = {}
    source_data: dict[bytes, bytes] = {}
    for text_name in sorted(files, key=lambda name: name.encode("utf-8")):
        require(
            Path(text_name).name == text_name
            and text_name not in {"", ".", ".."}
            and ":" not in text_name,
            f"XPCK accepts only safe top-level filenames: {text_name!r}",
        )
        name = text_name.encode("utf-8")
        require(b"\0" not in name, f"XPCK filename cannot contain NUL: {text_name}")
        checksum = crc32(name)
        if checksum in seen_crcs:
            previous = seen_crcs[checksum].decode("utf-8", errors="replace")
            raise ConversionError(f"XPCK filename CRC32 collision: {previous} / {text_name}")
        seen_crcs[checksum] = name
        names.append(name)
        source_data[name] = files[text_name]

    require(b"RES.bin" in source_data, "XPCK requires RES.bin")
    raw_res = source_data[b"RES.bin"]
    require(
        raw_res[:6] in {b"CHRC00", b"CHRC01"},
        "RES.bin must be uncompressed CHRC00 or CHRC01",
    )
    archived_data = dict(source_data)
    archived_data[b"RES.bin"] = level5_lz10_compress_canonical(raw_res)

    raw_name_table = bytearray()
    for name in names:
        require(len(raw_name_table) <= 0xFFFF, "XPCK name offset exceeds the 16-bit range")
        name_offsets[name] = len(raw_name_table)
        raw_name_table.extend(name)
        raw_name_table.append(0)
    require(len(raw_name_table) <= 0x10000, "Expanded XPCK name table exceeds 65536 bytes")

    compressed_names = bytearray(level5_lz10_compress_canonical(bytes(raw_name_table)))
    compressed_names.extend(bytes(-len(compressed_names) % 4))
    require(len(compressed_names) // 4 <= 0xFFFF, "Compressed XPCK name table exceeds the 16-bit range")

    data_region = bytearray()
    entries: list[XpckEntry] = []
    for name in names:
        payload = archived_data[name]
        require(len(payload) <= 0xFFFFFF, f"XPCK file size exceeds the 24-bit range: {name!r}")
        relative_offset = len(data_region)
        require(relative_offset % 4 == 0, "Internal error: XPCK data offset is not 4-byte aligned")
        require(relative_offset // 4 <= 0xFFFFFF, "XPCK data offset exceeds the 24-bit range")
        entries.append(XpckEntry(name, crc32(name), name_offsets[name], relative_offset, payload))
        data_region.extend(payload)
        data_region.extend(bytes(4 - (len(payload) % 4)))

    file_count = len(entries)
    info_offset = 20
    info_size = file_count * 12
    name_table_offset = info_offset + info_size
    data_offset = name_table_offset + len(compressed_names)
    require(
        name_table_offset % 4 == 0 and data_offset % 4 == 0,
        "Internal error: XPCK table offset is not 4-byte aligned",
    )
    require(data_offset // 4 <= 0xFFFF, "XPCK data-region offset exceeds the 16-bit range")

    info_table = bytearray()
    for entry in sorted(entries, key=lambda item: item.name_crc):
        offset4 = entry.data_offset // 4
        size = len(entry.data)
        info_table.extend(
            struct.pack(
                "<IHHHBB",
                entry.name_crc,
                entry.name_offset,
                offset4 & 0xFFFF,
                size & 0xFFFF,
                (offset4 >> 16) & 0xFF,
                (size >> 16) & 0xFF,
            )
        )

    index_bits = (file_count - 1).bit_length()
    packed_count = (index_bits << 12) | file_count
    header = b"XPCK" + struct.pack(
        "<6HI",
        packed_count,
        info_offset // 4,
        name_table_offset // 4,
        data_offset // 4,
        info_size // 4,
        len(compressed_names) // 4,
        len(data_region) // 4,
    )
    archive = header + bytes(info_table) + bytes(compressed_names) + bytes(data_region)
    require(len(archive) == data_offset + len(data_region), "Internal error: final XPCK size does not match")
    require(
        unpack_xpck_archive(archive) == files,
        "Internal error: files re-extracted from XPCK do not match the input files",
    )
    return archive


def pack_xpck_directory(input_dir: Path) -> bytes:
    """Build an XPCK archive from regular files directly in one directory."""

    require(input_dir.is_dir(), f"Input directory not found: {input_dir}")
    nested = [path.name for path in input_dir.iterdir() if path.is_dir()]
    require(not nested, "XPCK input contains subdirectories: " + ", ".join(sorted(nested)))
    paths = sorted(
        (path for path in input_dir.iterdir() if path.is_file()),
        key=lambda path: path.name.encode("utf-8"),
    )
    return pack_xpck_files({path.name: path.read_bytes() for path in paths})


MTN3_DESCRIPTOR_OFFSET = 0x64
MTN3_TRACK_COUNT = 4
MTN3_NAME_OFFSET = 0x2C
MTN3_FRAME_OFFSET = 0x58
MTN2_NAME_OFFSET = 0x28
MTN2_COMPRESSED_OFFSET = 0x58


def convert_mtn3(data: bytes) -> bytes:
    """Convert one YW3 XMTN/mtn3 payload into the YWB1 mtn2 layout."""

    require(len(data) >= MTN3_DESCRIPTOR_OFFSET, "mtn3 header is too short")
    require(data[:4] == b"XMTN", "mtn3 magic is not XMTN")

    counts = struct.unpack_from("<4I", data, 0x18)
    descriptor_count = sum(counts)
    hash_count = u32(data, 0x28)
    require(hash_count <= 0xFFFF, "mtn3 hash count cannot be represented by the 16-bit pointer table")

    compressed_offset = MTN3_DESCRIPTOR_OFFSET + descriptor_count * 16
    require(compressed_offset + 4 <= len(data), "mtn3 compressed region is out of range")
    source_raw = level5_decompress(data[compressed_offset:])

    used_size = u32(data, 0x10)
    source_data_offset = hash_count * 4 + MTN3_TRACK_COUNT * 8
    require(source_data_offset <= len(source_raw), "mtn3 hash/track table is out of range")
    require(
        used_size <= len(source_raw) - source_data_offset,
        "mtn3 used-data length exceeds the decompressed block",
    )

    track_pointer_offset = 12 + hash_count * 4
    track_records_offset = track_pointer_offset + MTN3_TRACK_COUNT * 2
    descriptor_table_offset = track_records_offset + MTN3_TRACK_COUNT * 8
    target_data_offset = descriptor_table_offset + descriptor_count * 16
    require(
        track_records_offset + (MTN3_TRACK_COUNT - 1) * 8 <= 0xFFFF,
        "mtn2 track-record offset exceeds the 16-bit range",
    )

    target_raw = bytearray(
        struct.pack("<3I", 12, track_pointer_offset, descriptor_table_offset)
    )
    target_raw.extend(source_raw[: hash_count * 4])
    for index in range(MTN3_TRACK_COUNT):
        target_raw.extend(p16(track_records_offset + index * 8))
    target_raw.extend(source_raw[hash_count * 4 : source_data_offset])

    for index in range(descriptor_count):
        source = MTN3_DESCRIPTOR_OFFSET + index * 16
        flag_offset, frame_offset, value_offset, extra = struct.unpack_from(
            "<4I", data, source
        )
        require(extra == 0, f"mtn3 descriptor {index} has an unknown fourth value: 0x{extra:X}")
        for label, relative_offset in (
            ("flag", flag_offset),
            ("frame", frame_offset),
            ("value", value_offset),
        ):
            require(
                relative_offset < used_size,
                f"mtn3 descriptor {index} {label} offset is outside the used-data region",
            )
        target_raw.extend(
            struct.pack(
                "<4I",
                flag_offset + target_data_offset,
                frame_offset + target_data_offset,
                value_offset + target_data_offset,
                0,
            )
        )

    target_raw.extend(source_raw[source_data_offset : source_data_offset + used_size])
    require(
        len(target_raw) == target_data_offset + used_size,
        "Internal error: mtn2 decompressed-block size does not match",
    )

    work_size = len(target_raw) + descriptor_count * 84
    output = bytearray(b"XMTN" + bytes(4))
    output.extend(p32(work_size))
    output.extend(p32(MTN2_NAME_OFFSET))
    output.extend(p32(MTN2_COMPRESSED_OFFSET))
    output.extend(data[0x18:0x2C])
    require(len(output) == MTN2_NAME_OFFSET, "Internal error: mtn2 name offset does not match")
    output.extend(data[MTN3_NAME_OFFSET:MTN3_FRAME_OFFSET])
    output.extend(data[MTN3_FRAME_OFFSET : MTN3_FRAME_OFFSET + 4])
    require(
        len(output) == MTN2_COMPRESSED_OFFSET,
        "Internal error: mtn2 compressed-block offset does not match",
    )
    output.extend(level5_lz10_compress(bytes(target_raw)))
    return bytes(output)


@dataclass(frozen=True)
class CharacterAnimationLayout:
    magic: bytes
    source_extension: str
    target_extension: str
    header_size: int
    count_fields: int
    track_count: int
    used_size_offset: int
    raw_base_offset: int
    target_work_offset: int
    target_name_offset: int
    target_compressed_offset: int


CHARACTER_ANIMATION_LAYOUTS = {
    ".mtn3": CharacterAnimationLayout(b"XMTN", ".mtn3", ".mtn2", 44, 4, 4, 0x10, 0x14, 8, 0x28, 0x58),
    ".mtm3": CharacterAnimationLayout(b"XMTM", ".mtm3", ".mtm2", 32, 2, 2, 0x10, 0x14, 16, 0x24, 0x54),
    ".imm3": CharacterAnimationLayout(b"XIMA", ".imm3", ".imm2", 40, 4, 4, 0x14, 0x10, 8, 0x24, 0x54),
}


def split_character_animation3(data: bytes, extension: str) -> list[bytes]:
    """Split bundled generation-3 headers and their shared decoded block.

    Header offsets 0x04/06 and 0x0C are relative to the end of *all*
    consecutive headers, whereas the raw-base field is relative to the one
    shared decoded block. Returning conventional single-entry sources keeps
    the existing standalone MTN API and its binary output unchanged.
    """

    layout = CHARACTER_ANIMATION_LAYOUTS[extension]
    headers: list[bytes] = []
    position = 0
    while data[position : position + 4] == layout.magic:
        require(position + layout.header_size <= len(data), f"{extension} bundled header is truncated")
        headers.append(data[position : position + layout.header_size])
        position += layout.header_size
    require(headers, f"{extension} magic does not match")
    body_base = position
    ranges: list[tuple[int, int, int, int, int]] = []
    previous_end = body_base
    for index, header in enumerate(headers):
        descriptor_count = sum(struct.unpack_from(f"<{layout.count_fields}I", header, 0x18))
        name_start = body_base + u32(header, 0x0C)
        track_start = body_base + u16(header, 4)
        descriptor_start = body_base + u16(header, 6)
        descriptor_end = descriptor_start + 16 * descriptor_count
        require(name_start == previous_end, f"{extension} entry {index}: name/body regions are not contiguous")
        require(track_start == name_start + 48, f"{extension} entry {index}: track-table offset is invalid")
        require(descriptor_start == track_start + 2 * layout.track_count,
                f"{extension} entry {index}: descriptor-table offset is invalid")
        require(descriptor_end <= len(data) - 4, f"{extension} entry {index}: descriptor table is out of range")
        hash_count = u32(header, 0x28) if extension == ".mtn3" else descriptor_count
        raw_prefix_size = hash_count * 4 + layout.track_count * 8
        require(u32(header, 8) == raw_prefix_size,
                f"{extension} entry {index}: hash/track-prefix size is inconsistent")
        ranges.append((name_start, descriptor_end, hash_count, raw_prefix_size, descriptor_count))
        previous_end = descriptor_end

    shared = level5_decompress(data[previous_end:])
    outputs: list[bytes] = []
    raw_previous_end = 0
    for index, (header, region) in enumerate(zip(headers, ranges)):
        name_start, descriptor_end, _, prefix_size, _ = region
        raw_start = u32(header, layout.raw_base_offset)
        used_size = u32(header, layout.used_size_offset)
        raw_end = raw_start + prefix_size + used_size
        require(raw_previous_end <= raw_start <= raw_end <= len(shared),
                f"{extension} entry {index}: bundled decoded-data range is invalid")
        require(not any(shared[raw_previous_end:raw_start]),
                f"{extension} entry {index}: unclaimed decoded-data gap is not zero-filled")
        raw_previous_end = raw_end
        if len(headers) == 1 and raw_start == 0:
            # The verified body offsets already have their standalone
            # values. Avoid a needless decode/recompress/decode cycle;
            # the v2 builder below still takes exactly used_size bytes.
            outputs.append(data)
            continue
        standalone = bytearray(header)
        struct.pack_into("<H", standalone, 4, 48)
        struct.pack_into("<H", standalone, 6, 48 + layout.track_count * 2)
        struct.pack_into("<I", standalone, 0x0C, 0)
        struct.pack_into("<I", standalone, layout.raw_base_offset, 0)
        standalone.extend(data[name_start:descriptor_end])
        standalone.extend(level5_lz10_compress(shared[raw_start:raw_end]))
        outputs.append(bytes(standalone))
    require(not any(shared[raw_previous_end:]), f"{extension}: decoded trailing padding is not zero-filled")
    return outputs


def convert_character_animation3(data: bytes, extension: str) -> list[bytes]:
    """Convert each MTN3/MTM3/IMM3 logical animation to an individual v2 file."""

    require(extension in CHARACTER_ANIMATION_LAYOUTS, f"Unsupported animation extension: {extension}")
    layout = CHARACTER_ANIMATION_LAYOUTS[extension]
    # Preserve the established standalone MTN output (including compression)
    # when no consecutive second XMTN header is present.
    if extension == ".mtn3" and data[44:48] != b"XMTN":
        return [convert_mtn3(data)]
    outputs: list[bytes] = []
    for source in split_character_animation3(data, extension):
        if extension == ".mtn3":
            outputs.append(convert_mtn3(source))
            continue
        counts = struct.unpack_from(f"<{layout.count_fields}I", source, 0x18)
        descriptor_count = sum(counts)
        hash_count = descriptor_count
        descriptor_start = layout.header_size + 48 + 2 * layout.track_count
        raw = level5_decompress(source[descriptor_start + 16 * descriptor_count:])
        used_size = u32(source, layout.used_size_offset)
        prefix_size = hash_count * 4 + layout.track_count * 8
        require(prefix_size + used_size <= len(raw), f"{extension} data length is out of range")
        pointer_start = 12 + hash_count * 4
        records_start = pointer_start + 2 * layout.track_count
        target_descriptor_start = records_start + 8 * layout.track_count
        target_data_start = target_descriptor_start + 16 * descriptor_count
        require(records_start + 8 * (layout.track_count - 1) <= 0xFFFF,
                f"{extension} track-record offset exceeds the 16-bit range")
        block = bytearray(struct.pack("<3I", 12, pointer_start, target_descriptor_start))
        block.extend(raw[:hash_count * 4])
        for i in range(layout.track_count):
            block.extend(p16(records_start + 8 * i))
        block.extend(raw[hash_count * 4:prefix_size])
        for i in range(descriptor_count):
            a, b, value, extra = struct.unpack_from("<4I", source, descriptor_start + 16 * i)
            require(extra == 0, f"{extension} descriptor {i} has an unknown fourth value: 0x{extra:X}")
            require(all(offset < used_size for offset in (a, b, value)),
                    f"{extension} descriptor {i} points outside the used-data region")
            block.extend(struct.pack("<4I", a + target_data_start, b + target_data_start,
                                     value + target_data_start, 0))
        block.extend(raw[prefix_size:prefix_size + used_size])
        work_size = len(block) + descriptor_count * 84
        output = bytearray(layout.magic + bytes(layout.target_work_offset - 4))
        output.extend(struct.pack("<3I", work_size, layout.target_name_offset, layout.target_compressed_offset))
        output.extend(source[0x18:0x18 + 4 * layout.count_fields])
        require(len(output) == layout.target_name_offset, "Internal animation name offset mismatch")
        output.extend(source[layout.header_size:layout.header_size + 48])
        require(len(output) == layout.target_compressed_offset, "Internal animation compressed offset mismatch")
        output.extend(level5_lz10_compress(bytes(block)))
        outputs.append(bytes(output))
    return outputs


def convert_mtn3_entries(data: bytes) -> list[bytes]:
    return convert_character_animation3(data, ".mtn3")


def convert_simple_inf2(data: bytes, extension: str) -> list[bytes]:
    """Convert MTMINF2/IMMINF2 only when every logical entry has no tail."""

    require(extension in {".mtminf2", ".imminf2"}, f"Unsupported simple INF2 extension: {extension}")
    outputs = []
    for index, entry in enumerate(parse_mtninf2(data)):
        require(entry.track_count == 0 and len(entry.body) == 68,
                f"{extension} entry {index}: unsupported special or additional payload")
        outputs.append(YWB1_MINF_PREFIX + entry.header[20:24] + entry.body)
    return outputs


def validate_character_animation2(
    data: bytes,
    extension: str,
    *,
    allow_name_alias: bool = False,
) -> bytes:
    """Validate an existing B1-layout animation and preserve its bytes."""

    reverse = {layout.target_extension: layout for layout in CHARACTER_ANIMATION_LAYOUTS.values()}
    require(extension in reverse, f"Unsupported existing animation extension: {extension}")
    layout = reverse[extension]
    require(len(data) >= layout.target_compressed_offset + 4, f"{extension} header is too short")
    require(data[:4] == layout.magic, f"{extension} magic does not match")
    require(not any(data[4:layout.target_work_offset]), f"{extension} reserved header is not zero-filled")
    require(u32(data, layout.target_work_offset + 4) == layout.target_name_offset,
            f"{extension} name offset does not match the B1 layout")
    require(u32(data, layout.target_work_offset + 8) == layout.target_compressed_offset,
            f"{extension} compressed offset does not match the B1 layout")
    counts_offset = layout.target_work_offset + 12
    descriptor_count = sum(struct.unpack_from(f"<{layout.count_fields}I", data, counts_offset))
    hash_count = u32(data, counts_offset + 4 * layout.count_fields) if extension == ".mtn2" else descriptor_count
    name_end = data.find(b"\0", layout.target_name_offset + 4, layout.target_compressed_offset - 4)
    require(name_end >= layout.target_name_offset + 4, f"{extension} animation name is not NUL-terminated")
    stored_name_id = u32(data, layout.target_name_offset)
    require(stored_name_id != 0, f"{extension} animation-name ID is zero")
    # Some official YW3 resources are renamed copies: y699000's IMM is
    # byte-identical to y159000 except the debug-name bytes, while retaining
    # y159000 IDs. Generation downgrade preserves both values. Do not
    # recalculate an identity field and break its MINF/RES references.
    require(allow_name_alias or crc32(data[layout.target_name_offset + 4:name_end]) == stored_name_id,
            f"{extension} animation-name CRC32 does not match")
    raw = level5_decompress(data[layout.target_compressed_offset:])
    pointer_start = 12 + hash_count * 4
    records_start = pointer_start + 2 * layout.track_count
    descriptor_start = records_start + 8 * layout.track_count
    data_start = descriptor_start + 16 * descriptor_count
    require(data_start <= len(raw), f"{extension} decoded tables are out of range")
    require(struct.unpack_from("<3I", raw) == (12, pointer_start, descriptor_start),
            f"{extension} decoded-table offsets do not match the B1 layout")
    require(struct.unpack_from(f"<{layout.track_count}H", raw, pointer_start) ==
            tuple(records_start + 8 * i for i in range(layout.track_count)),
            f"{extension} decoded track pointers are invalid")
    for i in range(descriptor_count):
        a, b, value, extra = struct.unpack_from("<4I", raw, descriptor_start + 16 * i)
        require(extra == 0 and all(data_start <= x < len(raw) for x in (a, b, value)),
                f"{extension} descriptor {i} is outside the decoded data")
    require(u32(data, layout.target_work_offset) == len(raw) + descriptor_count * 84,
            f"{extension} runtime work-size formula does not match")
    return data


def validate_character_inf(data: bytes, extension: str) -> bytes:
    """Validate an existing B1 MINF header/special region before copying it."""

    require(extension in {".mtninf", ".mtminf", ".imminf"}, f"Unsupported existing INF extension: {extension}")
    require(len(data) >= 96 and data[:4] == b"MINF", f"{extension} common header is invalid")
    require(data[4:12] == bytes(8) and u32(data, 12) == 28 and u32(data, 20) == 96,
            f"{extension} offsets do not match the B1 layout")
    name_end = data.find(b"\0", 0x20, 0x4C)
    require(name_end > 0x20, f"{extension} logical name is empty or not NUL-terminated")
    require(u32(data, 0x1C) == crc32(data[0x20:name_end]),
            f"{extension} logical-name CRC32 does not match")
    count = u32(data, 24)
    if count == 0:
        require(len(data) == 96 and u32(data, 16) == 0, f"{extension} has unexpected trailing data")
    else:
        require(extension == ".mtninf", f"{extension} special data is not supported")
        raw = level5_decompress(data[96:])
        require(count * 44 <= len(raw), f"{extension} special descriptor table is truncated")
        require(u32(data, 16) == len(raw) + 128 * count,
                f"{extension} runtime work-size formula does not match")
        for i in range(count):
            length, start, point, flag = struct.unpack_from("<4I", raw, 44 * i)
            require(length >= 48 and start >= count * 44 and start + length <= len(raw),
                    f"{extension} special descriptor {i} range is invalid")
            dynamic = u32(raw, start + 44)
            require(dynamic in {0, 1} and point == start + 48 + 4 * dynamic and flag == 0x10000,
                    f"{extension} special descriptor {i} fields are invalid")
            require(not any(raw[44 * i + 16:44 * (i + 1)]),
                    f"{extension} special descriptor {i} reserved fields are nonzero")
    return data


@dataclass(frozen=True)
class MtnInfDescriptor:
    payload_size: int
    shared_record_offset: int
    shared_payload_offset: int
    dynamic_count: int


@dataclass(frozen=True)
class MtnInf2Entry:
    header: bytes
    body: bytes

    @property
    def track_count(self) -> int:
        return u32(self.header, 0x14)


@dataclass(frozen=True)
class ParsedMtnInfTail:
    descriptors: tuple[MtnInfDescriptor, ...]
    fixed_values: bytes
    dynamic_prefix: bytes
    shared_compressed: bytes


YWB1_MINF_PREFIX = bytes.fromhex(
    "4d494e46 00000000 00000000 1c000000 00000000 60000000"
)


def parse_mtninf2(data: bytes) -> list[MtnInf2Entry]:
    headers: list[bytes] = []
    offsets: list[int] = []
    position = 0
    while position + 24 <= len(data) and data[position : position + 4] == b"MINF":
        header = data[position : position + 24]
        headers.append(header)
        offsets.append(u32(header, 8))
        position += 24

    require(headers, "No MINF2 headers were found")
    require(offsets == sorted(offsets), "MINF2 body offsets are not in ascending order")
    body_area_size = len(data) - position
    entries: list[MtnInf2Entry] = []
    for index, (header, offset) in enumerate(zip(headers, offsets)):
        end = offsets[index + 1] if index + 1 < len(offsets) else body_area_size
        require(0 <= offset <= end <= body_area_size, f"Entry {index} body offset is out of range")
        body = data[position + offset : position + end]
        require(len(body) >= 68, f"Entry {index} body is shorter than 68 bytes")
        entries.append(MtnInf2Entry(header, body))
    return entries


def parse_mtninf_tail(entry: MtnInf2Entry, index: int) -> ParsedMtnInfTail:
    count = entry.track_count
    tail = entry.body[68:]
    descriptor_size = count * 16
    fixed_size = count * 12
    require(
        descriptor_size + fixed_size <= len(tail),
        f"Entry {index}: special MTNINF track region ends prematurely",
    )

    descriptors: list[MtnInfDescriptor] = []
    for descriptor_index in range(count):
        values = struct.unpack_from("<4I", tail, descriptor_index * 16)
        descriptor = MtnInfDescriptor(*values)
        if descriptor.dynamic_count == 0:
            require(
                descriptor.payload_size == 0,
                f"Entry {index}, descriptor {descriptor_index}: unknown fixed type A={descriptor.payload_size}",
            )
            require(
                descriptor.shared_payload_offset == descriptor.shared_record_offset,
                f"Entry {index}, descriptor {descriptor_index}: fixed-type B/C values do not match",
            )
        elif descriptor.dynamic_count == 1:
            # The paired x381000_p84 B1 descriptor proves the 4-byte
            # integer payload for event 0x05E4. A=4 for other event types
            # (notably x611000 event 0x044E) has a different auxiliary
            # layout and remains unsupported.
            event_type = u32(tail, descriptor_size + descriptor_index * 12 + 8)
            require(
                descriptor.payload_size in {8, 12}
                or (descriptor.payload_size == 4 and event_type == 0x05E4),
                f"Entry {index}, descriptor {descriptor_index}: unknown dynamic type A={descriptor.payload_size}",
            )
            require(
                descriptor.shared_payload_offset == descriptor.shared_record_offset + 4,
                f"Entry {index}, descriptor {descriptor_index}: dynamic-type C is not B+4",
            )
        else:
            raise ConversionError(
                f"Entry {index}, descriptor {descriptor_index}: unsupported D={descriptor.dynamic_count}"
            )
        descriptors.append(descriptor)

    fixed_offset = descriptor_size
    fixed_values = tail[fixed_offset : fixed_offset + fixed_size]
    dynamic_descriptors = [d for d in descriptors if d.dynamic_count == 1]
    prefix_offset = fixed_offset + fixed_size
    prefix_size = len(dynamic_descriptors) * 4
    require(prefix_offset + prefix_size <= len(tail), f"Entry {index}: dynamic auxiliary values are missing")
    dynamic_prefix = tail[prefix_offset : prefix_offset + prefix_size]
    prefix_values = tuple(
        u32(dynamic_prefix, offset) for offset in range(0, len(dynamic_prefix), 4)
    )
    expected_prefix = tuple(d.payload_size for d in dynamic_descriptors)
    require(
        prefix_values == expected_prefix,
        f"Entry {index}: dynamic auxiliary values {prefix_values} do not match descriptors {expected_prefix}",
    )

    return ParsedMtnInfTail(
        tuple(descriptors),
        fixed_values,
        dynamic_prefix,
        tail[prefix_offset + prefix_size :],
    )


def collect_shared_data(parsed_tails: Sequence[ParsedMtnInfTail]) -> bytes:
    compressed_blocks = [tail.shared_compressed for tail in parsed_tails if tail.shared_compressed]
    require(len(compressed_blocks) <= 1, "Multiple shared compressed regions prevent a unique reference base")
    shared = level5_decompress(compressed_blocks[0]) if compressed_blocks else b""

    has_dynamic = any(
        descriptor.dynamic_count == 1
        for tail in parsed_tails
        for descriptor in tail.descriptors
    )
    require(not has_dynamic or bool(shared), "Dynamic MTNINF descriptors exist, but no shared compressed region exists")
    return shared


def build_ywb1_special_block(
    parsed: ParsedMtnInfTail,
    shared: bytes,
    entry_index: int,
) -> bytes:
    descriptors = parsed.descriptors
    if not descriptors:
        return b""

    dynamic_count = sum(d.dynamic_count for d in descriptors)
    lengths = [0x30 + d.payload_size + 4 * d.dynamic_count for d in descriptors]
    position = 44 * len(descriptors) + 4 * dynamic_count
    output = bytearray()

    for descriptor_index, (descriptor, length) in enumerate(zip(descriptors, lengths)):
        output.extend(
            struct.pack(
                "<4I",
                length,
                position,
                position + 0x30 + 4 * descriptor.dynamic_count,
                0x00010000,
            )
        )
        output.extend(bytes(28))
        position += length

        if descriptor.dynamic_count:
            record_end = descriptor.shared_record_offset + 4 + descriptor.payload_size
            require(
                record_end <= len(shared),
                f"Entry {entry_index}, descriptor {descriptor_index}: shared-data reference is out of range",
            )
            payload = shared[descriptor.shared_payload_offset:record_end]
            require(
                descriptor.payload_size == 4 or b"\0" in payload,
                f"Entry {entry_index}, descriptor {descriptor_index}: shared string is not NUL-terminated",
            )

    output.extend(parsed.dynamic_prefix)
    for descriptor_index, descriptor in enumerate(descriptors):
        value = parsed.fixed_values[descriptor_index * 12 : descriptor_index * 12 + 12]
        require(len(value) == 12, f"Entry {entry_index}, descriptor {descriptor_index}: base value is incomplete")
        output.extend(value)
        if descriptor.dynamic_count == 0:
            output.extend(bytes(36))
        else:
            record_end = descriptor.shared_record_offset + 4 + descriptor.payload_size
            output.extend(bytes(32))
            output.extend(p32(descriptor.dynamic_count))
            output.extend(shared[descriptor.shared_record_offset:record_end])

    require(len(output) == position, f"Entry {entry_index}: internal special-expansion size calculation does not match")
    return bytes(output)


def convert_mtninf2(data: bytes) -> list[bytes]:
    entries = parse_mtninf2(data)
    parsed_tails = [parse_mtninf_tail(entry, index) for index, entry in enumerate(entries)]
    shared = collect_shared_data(parsed_tails)
    outputs: list[bytes] = []

    for index, (entry, parsed) in enumerate(zip(entries, parsed_tails)):
        special_raw = build_ywb1_special_block(parsed, shared, index)
        output = bytearray(YWB1_MINF_PREFIX)
        if special_raw:
            # YWB1 reserves an additional 0x80 bytes of runtime work memory
            # for every expanded special track.
            work_size = len(special_raw) + 0x80 * entry.track_count
            struct.pack_into("<I", output, 0x10, work_size)
        output.extend(entry.header[0x14:0x18])
        output.extend(entry.body[:68])
        require(len(output) == 0x60, f"Entry {index}: YWB1 common region is not 0x60 bytes")
        if special_raw:
            output.extend(level5_lz10_compress(special_raw))
        outputs.append(bytes(output))
    return outputs


@dataclass(frozen=True)
class ResSection:
    type_id: int
    stride: int
    records: tuple[bytes, ...]


@dataclass(frozen=True)
class ParsedRes:
    unknown0: int
    unknown1: int
    strings: tuple[bytes, ...]
    material_sections: tuple[ResSection, ...]
    node_sections: tuple[ResSection, ...]


def parse_res(data: bytes) -> ParsedRes:
    """Parse an uncompressed CHRC00/01/02 RES.bin."""

    require(len(data) >= 20, "RES.bin header is too short")
    require(
        data[:6] in {b"CHRC00", b"CHRC01", b"CHRC02"},
        "RES.bin CHRC magic is invalid",
    )
    unknown0, strings4, unknown1, material4, material_count, node4, node_count = (
        struct.unpack_from("<7H", data, 6)
    )
    string_offset = strings4 * 4
    material_table_offset = material4 * 4
    node_table_offset = node4 * 4
    require(string_offset <= len(data), "RES string-table offset is out of range")

    strings: list[bytes] = []
    position = string_offset
    while position < len(data):
        end = data.find(b"\0", position)
        require(end >= 0, "RES string is not NUL-terminated")
        if end == position:
            require(
                not any(data[position:]),
                "RES string table contains nonzero data after its terminator",
            )
            break
        strings.append(data[position:end])
        position = end + 1

    def read_sections(table_offset: int, count: int, table_name: str) -> tuple[ResSection, ...]:
        require(
            table_offset + count * 8 <= len(data),
            f"RES {table_name} section table is out of range",
        )
        result: list[ResSection] = []
        for index in range(count):
            offset4, record_count, type_id, stride = struct.unpack_from(
                "<4H", data, table_offset + index * 8
            )
            if type_id == 0x270F:
                require(
                    record_count == 0 and stride == 0,
                    f"RES {table_name} sentinel {index} is not empty",
                )
                result.append(ResSection(type_id, 0, ()))
                continue

            require(stride > 0, f"RES section 0x{type_id:04X} has a zero record size")
            offset = offset4 * 4
            end = offset + record_count * stride
            require(end <= len(data), f"RES section 0x{type_id:04X} is out of range")
            records = tuple(
                data[offset + item * stride : offset + (item + 1) * stride]
                for item in range(record_count)
            )
            result.append(ResSection(type_id, stride, records))
        return tuple(result)

    return ParsedRes(
        unknown0,
        unknown1,
        tuple(strings),
        read_sections(material_table_offset, material_count, "material"),
        read_sections(node_table_offset, node_count, "node"),
    )


def mtninf2_names(data: bytes) -> list[bytes]:
    """Read the raw logical names used by RES from an MTNINF2 bundle."""

    names: list[bytes] = []
    for index, entry in enumerate(parse_mtninf2(data)):
        end = entry.body.find(b"\0", 4, 48)
        require(end > 4, f"MTNINF2 entry {index} name is empty or not NUL-terminated")
        require(u32(entry.body, 0) == crc32(entry.body[4:end]),
                f"MTNINF2 entry {index} logical-name CRC32 does not match")
        names.append(entry.body[4:end])
    return names


CHARACTER_ROOT_NAME = b"out_00"
CHARACTER_BASE_RES_TYPES = {0x012D: 0x012C, 0x0137: 0x0136, 0x0141: 0x0140}
CHARACTER_INF_RES_TYPES = {0x0191: 0x0190, 0x019B: 0x019A, 0x01A5: 0x01A4}
CHARACTER_BASE_RES_EXTENSIONS = {0x012D: ".mtn2", 0x0137: ".imm2", 0x0141: ".mtm2"}
CHARACTER_INF_RES_EXTENSIONS = {0x0191: ".mtninf2", 0x019B: ".imminf2", 0x01A5: ".mtminf2"}


def convert_character_res(
    data: bytes,
    mtninf2_data: bytes | None = None,
    version: int = 1,
    *,
    animation_files: dict[str, bytes] | None = None,
    inf2_files: dict[str, bytes] | None = None,
) -> bytes:
    """Convert character RES, rebuilding every animation category's links.

    The positional standalone API remains compatible. The archive pipeline
    supplies converted animations and source INF2 bundles so multi-root MTN,
    MTM and IMM records use their actual logical names, never a global root.
    Already-old CHRC00/01 references are checked and preserved.
    """

    require(version in {0, 1}, f"RES output version must be 0 or 1: {version}")
    parsed = parse_res(data)
    all_sections = parsed.material_sections + parsed.node_sections
    require(not any(section.type_id == 0x0123 for section in all_sections),
            "RES model section 0x0123 has no established B1 conversion rule")
    for newer, older in {**CHARACTER_BASE_RES_TYPES, **CHARACTER_INF_RES_TYPES}.items():
        matching = [section for section in all_sections if section.type_id in {newer, older}]
        require(len(matching) <= 1, f"RES has duplicate old/new animation section 0x{older:04X}")
        for section in matching:
            if section.type_id == newer:
                require(section.stride == 28 and len(section.records) == 1,
                        f"RES section 0x{newer:04X} must contain one 28-byte bundle reference")
            else:
                require(section.stride == 8 and all(u32(record, 4) == 0 for record in section.records),
                        f"RES section 0x{older:04X} has invalid legacy record size/reserved fields")
    strings = list(parsed.strings)
    bundles = dict(inf2_files or {})
    if mtninf2_data is not None:
        existing = [raw for name, raw in bundles.items() if Path(name).suffix.lower() == ".mtninf2"]
        require(not existing or existing == [mtninf2_data], "Conflicting MTNINF2 inputs for RES conversion")
        if not existing:
            bundles["000.mtninf2"] = mtninf2_data

    def remember(names: Sequence[bytes]) -> None:
        for name in names:
            if name not in strings:
                strings.append(name)

    roots: dict[str, list[bytes]] = {}
    root_records: dict[str, tuple[bytes, ...]] = {}
    old_inf_names: dict[str, list[bytes]] = {}
    if animation_files is not None:
        for layout in CHARACTER_ANIMATION_LAYOUTS.values():
            names = _numbered_names(animation_files, layout.target_extension)
            roots[layout.target_extension] = []
            identifiers = []
            for name in names:
                raw = validate_character_animation2(animation_files[name], layout.target_extension,
                                                    allow_name_alias=bool(bundles))
                start = layout.target_name_offset + 4
                end = raw.find(b"\0", start, layout.target_compressed_offset - 4)
                require(end >= start, f"RES animation name is not NUL-terminated: {name}")
                roots[layout.target_extension].append(raw[start:end])
                identifiers.append(struct.pack("<II", u32(raw, layout.target_name_offset), 0))
            root_records[layout.target_extension] = tuple(identifiers)
        for extension in (".mtninf", ".mtminf", ".imminf"):
            old_inf_names[extension] = []
            for name in _numbered_names(animation_files, extension):
                raw = validate_character_inf(animation_files[name], extension)
                end = raw.find(b"\0", 0x20, 0x4C)
                require(end > 0x20, f"RES logical INF name is empty or unterminated: {name}")
                old_inf_names[extension].append(raw[0x20:end])

    def logical_inf_names(extension: str) -> list[bytes]:
        candidates = [raw for name, raw in sorted(bundles.items()) if Path(name).suffix.lower() == extension]
        require(len(candidates) == 1, f"RES {extension} conversion requires exactly one bundle from the same archive")
        return mtninf2_names(candidates[0])

    def references(names: Sequence[bytes]) -> tuple[bytes, ...]:
        return tuple(struct.pack("<II", crc32(name), 0) for name in names)

    def convert_sections(sections: Sequence[ResSection]) -> list[ResSection]:
        converted: list[ResSection] = []
        for section in sections:
            if section.type_id in CHARACTER_BASE_RES_TYPES:
                extension = CHARACTER_BASE_RES_EXTENSIONS[section.type_id]
                if animation_files is None:
                    require(section.type_id == 0x012D and len(section.records) == 1,
                            "RES multiple/category-specific animation roots require converted animation files")
                    root_names = [CHARACTER_ROOT_NAME]
                else:
                    root_names = roots[extension]
                    # The newer RES record names the physical bundle. Its
                    # one record expands to every logical animation root.
                    require(section.stride == 28 and len(section.records) == 1 and root_names,
                            f"RES {extension} requires one physical bundle reference and nonempty converted animations")
                remember(root_names)
                converted.append(
                    ResSection(
                        CHARACTER_BASE_RES_TYPES[section.type_id],
                        8,
                        references(root_names) if animation_files is None else root_records[extension],
                    )
                )
            elif section.type_id in CHARACTER_INF_RES_TYPES:
                require(section.stride == 28 and len(section.records) == 1,
                        f"RES section 0x{section.type_id:04X} must contain one 28-byte bundle reference")
                inf_names = logical_inf_names(CHARACTER_INF_RES_EXTENSIONS[section.type_id])
                remember(inf_names)
                converted.append(
                    ResSection(
                        CHARACTER_INF_RES_TYPES[section.type_id],
                        8,
                        references(inf_names),
                    )
                )
            else:
                if animation_files is not None:
                    for newer, older in CHARACTER_BASE_RES_TYPES.items():
                        if section.type_id == older:
                            expected = root_records[CHARACTER_BASE_RES_EXTENSIONS[newer]]
                            require(section.stride == 8 and section.records == expected,
                                    f"Existing RES animation references 0x{older:04X} do not match animation files")
                    for newer, older in CHARACTER_INF_RES_TYPES.items():
                        if section.type_id == older:
                            extension = CHARACTER_INF_RES_EXTENSIONS[newer][:-1]
                            expected = references(old_inf_names[extension])
                            require(section.stride == 8 and section.records == expected,
                                    f"Existing RES INF references 0x{older:04X} do not match INF files")
                converted.append(section)
        return converted

    materials = convert_sections(parsed.material_sections)
    nodes = convert_sections(parsed.node_sections)
    if animation_files is not None:
        sections = materials + nodes
        for newer, older in CHARACTER_BASE_RES_TYPES.items():
            expected = root_records[CHARACTER_BASE_RES_EXTENSIONS[newer]]
            matches = [section for section in sections if section.type_id == older]
            require(len(matches) == (1 if expected else 0),
                    f"RES animation section 0x{older:04X} presence/count does not match converted files")
            if matches:
                require(matches[0].stride == 8 and matches[0].records == expected,
                        f"RES animation section 0x{older:04X} references do not match converted files")
        for newer, older in CHARACTER_INF_RES_TYPES.items():
            extension = CHARACTER_INF_RES_EXTENSIONS[newer][:-1]
            expected = references(old_inf_names[extension])
            matches = [section for section in sections if section.type_id == older]
            require(len(matches) == (1 if expected else 0),
                    f"RES INF section 0x{older:04X} presence/count does not match converted files")
            if matches:
                require(matches[0].stride == 8 and matches[0].records == expected,
                        f"RES INF section 0x{older:04X} references do not match converted files")
    material_table_offset = 20
    node_table_offset = material_table_offset + len(materials) * 8
    data_offset = node_table_offset + len(nodes) * 8
    material_table = bytearray()
    node_table = bytearray()
    payload = bytearray()

    def append_sections(sections: Sequence[ResSection], table: bytearray) -> None:
        nonlocal data_offset
        for section in sections:
            require(data_offset % 4 == 0, "RES section offset is not 4-byte aligned")
            require(data_offset // 4 <= 0xFFFF, "RES section offset exceeds the 16-bit range")
            require(len(section.records) <= 0xFFFF, "RES record count exceeds the 16-bit range")
            require(section.stride <= 0xFFFF, "RES record size exceeds the 16-bit range")
            if section.type_id == 0x270F:
                table.extend(struct.pack("<4H", data_offset // 4, 0, 0x270F, 0))
                continue

            table.extend(
                struct.pack(
                    "<4H",
                    data_offset // 4,
                    len(section.records),
                    section.type_id,
                    section.stride,
                )
            )
            raw = b"".join(section.records)
            require(
                len(raw) == len(section.records) * section.stride,
                f"RES section 0x{section.type_id:04X} record size does not match",
            )
            payload.extend(raw)
            data_offset += len(raw)

    append_sections(materials, material_table)
    append_sections(nodes, node_table)
    require(data_offset % 4 == 0, "RES string-table offset is not 4-byte aligned")
    require(data_offset // 4 <= 0xFFFF, "RES string-table offset exceeds the 16-bit range")
    string_offset = data_offset
    string_data = b"".join(raw + b"\0" for raw in strings)
    string_data += bytes(-len(string_data) % 4)

    header = f"CHRC0{version}".encode("ascii") + struct.pack(
        "<7H",
        parsed.unknown0,
        string_offset // 4,
        parsed.unknown1,
        material_table_offset // 4,
        len(materials),
        node_table_offset // 4,
        len(nodes),
    )
    return bytes(header + material_table + node_table + payload + string_data)


def _numbered_names(files: dict[str, bytes], suffix: str) -> list[str]:
    """Return one extension's names after enforcing 000.ext, 001.ext, ... order."""

    names = sorted(
        (name for name in files if Path(name).suffix.lower() == suffix),
        key=lambda name: name.encode("utf-8"),
    )
    expected = [f"{index:03d}{suffix}" for index in range(len(names))]
    require(
        names == expected,
        f"{suffix} filenames are not sequential from 000 "
        f"(found: {', '.join(names) or 'none'})",
    )
    return names


def _res_section(
    sections: Sequence[ResSection],
    type_id: int,
    expected_count: int,
    expected_stride: int,
    label: str,
) -> ResSection | None:
    """Find and validate a resource-reference section for one p00 file kind."""

    matches = [section for section in sections if section.type_id == type_id]
    if expected_count == 0:
        require(not matches, f"RES contains unexpected {label} section 0x{type_id:04X}")
        return None
    require(len(matches) == 1, f"RES does not contain exactly one {label} section 0x{type_id:04X}")
    section = matches[0]
    require(
        section.stride == expected_stride,
        f"RES {label} section record size is not {expected_stride}",
    )
    require(
        len(section.records) == expected_count,
        f"RES {label} record count does not match the number of internal files "
        f"(RES: {len(section.records)}, files: {expected_count})",
    )
    return section


def convert_p00_internal_files(
    files: dict[str, bytes],
    res_version: int = 1,
) -> dict[str, bytes]:
    """Convert and validate an in-memory p00 model internal-file set."""

    require(files, "p00 contains no internal files")
    require(res_version in {0, 1}, f"RES output version must be 0 or 1: {res_version}")
    for name in files:
        require(
            Path(name).name == name and name not in {"", ".", ".."},
            f"p00 contains an unsafe internal filename: {name!r}",
        )

    names = sorted(files, key=lambda name: name.encode("utf-8"))
    res_names = [name for name in names if name.lower() == "res.bin"]
    require(len(res_names) == 1, f"Exactly one RES.bin is required (found: {len(res_names)})")
    supported = {".atr", ".cmn", ".lkat", ".mbn", ".mtr", ".prm", ".sil", ".txp", ".xi"}
    for name in names:
        if name in res_names:
            continue
        require(
            Path(name).suffix.lower() in supported,
            f"Unsupported p00 internal file: {name}",
        )

    by_suffix = {suffix: _numbered_names(files, suffix) for suffix in supported}
    # B1 includes bone/parameter-only model archives and models with zero or
    # multiple textures, projections and LKAT files. Validate resource-table
    # counts instead of imposing the original ten-sample cardinalities.
    # Bone-less model support has not been established in the B1 corpus.
    for suffix in (".cmn", ".mbn"):
        require(by_suffix[suffix], f"p00 does not contain a {suffix} file")

    parsed_res = parse_res(files[res_names[0]])
    require(not any(s.type_id == 0x0123 for s in parsed_res.material_sections),
            "RES model section 0x0123 has no established B1 conversion rule")
    string_crcs = {crc32(raw) for raw in parsed_res.strings}

    material_links = {
        ".atr": _res_section(parsed_res.material_sections, 0x00DC, len(by_suffix[".atr"]), 8, "ATR"),
        ".mtr": _res_section(parsed_res.material_sections, 0x00E6, len(by_suffix[".mtr"]), 8, "MTR"),
        ".xi": _res_section(parsed_res.material_sections, 0x00F0, len(by_suffix[".xi"]), 20, "XI"),
    }
    node_links = {
        ".prm": _res_section(parsed_res.node_sections, 0x0064, len(by_suffix[".prm"]), 8, "PRM"),
        ".mbn": _res_section(parsed_res.node_sections, 0x006E, len(by_suffix[".mbn"]), 8, "MBN"),
        ".sil": _res_section(parsed_res.node_sections, 0x0078, len(by_suffix[".sil"]), 8, "SIL"),
        ".txp": _res_section(parsed_res.node_sections, 0x008C, len(by_suffix[".txp"]), 8, "TXP"),
        ".cmn": _res_section(parsed_res.node_sections, 0x00C8, len(by_suffix[".cmn"]), 8, "CMN"),
        ".lkat": _res_section(parsed_res.node_sections, 0x01CC, len(by_suffix[".lkat"]), 8, "LKAT"),
    }
    # Keep the local names so static analysis and future extensions make it
    # explicit that the material-side sections were also validated above.
    # A missing material kind is valid if both its files and RES section are
    # absent; _res_section already verified that correspondence.

    outputs: dict[str, bytes] = {}
    converters = {
        ".atr": convert_character_atr,
        ".cmn": convert_character_cmn,
        ".lkat": convert_character_lkat,
        ".mbn": convert_character_mbn,
        ".mtr": convert_character_mtr,
        ".prm": convert_character_prm,
        ".sil": convert_character_sil,
        ".txp": convert_character_txp,
        ".xi": convert_character_xi,
    }
    for name in names:
        suffix = Path(name).suffix.lower()
        if suffix in converters:
            outputs[name] = converters[suffix](files[name])

    mbn_section = node_links[".mbn"]
    assert mbn_section is not None
    mbn_ids: set[int] = set()
    root_count = 0
    for index, (name, record) in enumerate(zip(by_suffix[".mbn"], mbn_section.records)):
        data = files[name]
        node_id, parent_id = struct.unpack_from("<2I", data, 0)
        res_id, res_reserved = struct.unpack("<2I", record)
        require(res_id == node_id and res_reserved == 0, f"RES and {name} MBN node IDs do not match")
        require(node_id not in mbn_ids, f"Duplicate MBN node ID: {name}")
        if parent_id == 0:
            root_count += 1
            require(index == 0, f"MBN root is not 000.mbn: {name}")
        else:
            require(parent_id in mbn_ids, f"The parent MBN node for {name} does not appear earlier")
        mbn_ids.add(node_id)
    require(root_count == 1, f"Expected exactly one MBN root node (found: {root_count})")

    txp_section = node_links[".txp"]
    if txp_section is not None:
        for name, record in zip(by_suffix[".txp"], txp_section.records):
            projection_crc, material_crc = struct.unpack_from("<2I", files[name], 0)
            res_crc, res_reserved = struct.unpack("<2I", record)
            require(
                projection_crc == res_crc and res_reserved == 0,
                f"RES and {name} TXP projection-name CRC32 values do not match",
            )
            require(
                projection_crc in string_crcs and material_crc in string_crcs,
                f"The TXP reference name for {name} is missing from the RES string table",
            )

    cmn_section = node_links[".cmn"]
    assert cmn_section is not None
    for name, record in zip(by_suffix[".cmn"], cmn_section.records):
        data = files[name]
        parameter_crc = u32(data, 0x04)
        res_crc, total_size, extra_size = struct.unpack("<IHH", record)
        require(res_crc == parameter_crc, f"RES and {name} CMN parameter CRC32 values do not match")
        require(parameter_crc in string_crcs, f"The CMN parameter name for {name} is missing from the RES string table")
        expected_total = len(data) if len(data) > 12 else 0
        expected_extra = len(data) - 12 if len(data) > 12 else 0
        require(
            (total_size, extra_size) == (expected_total, expected_extra),
            f"RES and {name} CMN variable-length metadata do not match",
        )
        # Type-2 array values may reference objects outside this RES string
        # table. Native B1 MESH_DRAW_ALP0/SHADOW records prove this is valid.
        # convert_character_cmn still checks every element's type and value;
        # external resolution is a game-context check, not a local CRC check.

    outputs["RES.bin"] = convert_character_res(files[res_names[0]], None, res_version)
    require(set(outputs) == (set(files) - set(res_names)) | {"RES.bin"}, "p00 output file set does not match the input")
    return outputs


def build_p00_content_outputs(source_dir: Path, res_version: int = 1) -> dict[str, bytes]:
    """Build converted files from one extracted p00 content folder."""

    require(source_dir.is_dir(), f"Input directory not found: {source_dir}")
    nested = [path.name for path in source_dir.iterdir() if path.is_dir()]
    require(not nested, "p00 input contains subdirectories: " + ", ".join(sorted(nested)))
    paths = sorted(
        (path for path in source_dir.iterdir() if path.is_file()),
        key=lambda path: path.name.encode("utf-8"),
    )
    return convert_p00_internal_files(
        {path.name: path.read_bytes() for path in paths},
        res_version,
    )


def convert_p8_internal_files(
    files: dict[str, bytes],
    res_version: int = 1,
) -> dict[str, bytes]:
    """Convert an in-memory p80/p84 internal-file set.

    Keeping this core independent from directories and XC files allows the
    future p00/p80/p84 set converter to dispatch all three archive slots into
    their respective internal converters without temporary files.
    """

    require(files, "p80/p84 contains no internal files")
    require(res_version in {0, 1}, f"RES output version must be 0 or 1: {res_version}")
    for name in files:
        require(
            Path(name).name == name and name not in {"", ".", ".."},
            f"p80/p84 contains an unsafe internal filename: {name!r}",
        )

    names = sorted(files, key=lambda name: name.encode("utf-8"))
    res_names = [name for name in names if name.lower() == "res.bin"]
    require(len(res_names) == 1, f"Exactly one RES.bin is required (found: {len(res_names)})")

    supported = {
        ".mtn3", ".mtm3", ".imm3", ".mtninf2", ".mtminf2", ".imminf2",
        ".mtn2", ".mtm2", ".imm2", ".mtninf", ".mtminf", ".imminf",
        ".cmn", ".lkat", ".sil",
    }
    for name in names:
        if name in res_names:
            continue
        require(
            Path(name).suffix.lower() in supported,
            f"Unsupported p80/p84 internal file: {name}",
        )

    outputs: dict[str, bytes] = {}

    def put(name: str, payload: bytes, source_name: str) -> None:
        require(name not in outputs, f"Output filename collision: {name} (source: {source_name})")
        outputs[name] = payload

    inf2_files: dict[str, bytes] = {}
    for extension, layout in CHARACTER_ANIMATION_LAYOUTS.items():
        bundled = _numbered_names(files, extension)
        existing = _numbered_names(files, layout.target_extension)
        require(len(bundled) <= 1, f"At most one {extension} bundle is supported (found: {len(bundled)})")
        require(not (bundled and existing), f"p80/p84 mixes {extension} and {layout.target_extension}")
        if extension == ".mtn3":
            require(bundled or existing, "p80/p84 does not contain .mtn3 or .mtn2 animation data")
        for name in bundled:
            try:
                converted = convert_character_animation3(files[name], extension)
            except ConversionError as error:
                raise ConversionError(f"Failed to convert {name}: {error}") from error
            for index, payload in enumerate(converted):
                validate_character_animation2(payload, layout.target_extension, allow_name_alias=True)
                put(f"{index:03d}{layout.target_extension}", payload, name)
        for name in existing:
            put(name, validate_character_animation2(files[name], layout.target_extension), name)

    for extension in (".mtninf2", ".mtminf2", ".imminf2"):
        target_extension = extension[:-1]
        bundled = _numbered_names(files, extension)
        existing = _numbered_names(files, target_extension)
        require(len(bundled) <= 1, f"At most one {extension} bundle is supported (found: {len(bundled)})")
        require(not (bundled and existing), f"p80/p84 mixes {extension} and {target_extension}")
        if extension == ".mtninf2":
            require(bundled or existing, "p80/p84 does not contain .mtninf2 or .mtninf data")
        for name in bundled:
            inf2_files[name] = files[name]
            try:
                converted = (convert_mtninf2(files[name]) if extension == ".mtninf2"
                             else convert_simple_inf2(files[name], extension))
            except ConversionError as error:
                raise ConversionError(f"Failed to convert {name}: {error}") from error
            for index, payload in enumerate(converted):
                validate_character_inf(payload, target_extension)
                put(f"{index:03d}{target_extension}", payload, name)
        for name in existing:
            put(name, validate_character_inf(files[name], target_extension), name)

    extra_converters = {".cmn": convert_character_cmn, ".lkat": convert_character_lkat,
                        ".sil": convert_character_sil}
    for name in names:
        suffix = Path(name).suffix.lower()
        if suffix in extra_converters:
            put(name, extra_converters[suffix](files[name]), name)

    res_name = res_names[0]
    put(
        "RES.bin",
        convert_character_res(files[res_name], None, res_version,
                              animation_files=outputs, inf2_files=inf2_files),
        res_name,
    )

    return outputs


def build_p8_content_outputs(source_dir: Path, res_version: int = 1) -> dict[str, bytes]:
    """Build converted files from one extracted p80/p84 content folder."""

    require(source_dir.is_dir(), f"Input directory not found: {source_dir}")
    nested = [path.name for path in source_dir.iterdir() if path.is_dir()]
    require(not nested, "p80/p84 input contains subdirectories: " + ", ".join(sorted(nested)))
    paths = sorted(
        (path for path in source_dir.iterdir() if path.is_file()),
        key=lambda path: path.name.encode("utf-8"),
    )
    return convert_p8_internal_files(
        {path.name: path.read_bytes() for path in paths},
        res_version,
    )


def write_outputs(outputs: Sequence[bytes], output_dir: Path, overwrite: bool) -> list[Path]:
    output_dir = output_dir.resolve()
    destinations = [output_dir / f"{index:03d}.mtninf" for index in range(len(outputs))]
    if not overwrite:
        existing = [path for path in destinations if path.exists()]
        if existing:
            raise ConversionError(f"Output file already exists: {existing[0]}")

    output_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".mtninf2-", dir=output_dir))
    try:
        for index, payload in enumerate(outputs):
            (staging / f"{index:03d}.mtninf").write_bytes(payload)
        for source, destination in zip(sorted(staging.iterdir()), destinations):
            os.replace(source, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destinations


def convert_mtninf2_file(input_path: Path, output_dir: Path, overwrite: bool = False) -> list[Path]:
    require(input_path.is_file(), f"Input file not found: {input_path}")
    outputs = convert_mtninf2(input_path.read_bytes())
    return write_outputs(outputs, output_dir, overwrite)


def write_single_output(payload: bytes, output_path: Path, overwrite: bool) -> Path:
    """Atomically write one converted file without overwriting by default."""

    output_path = output_path.resolve()
    if output_path.exists() and not overwrite:
        raise ConversionError(f"Output file already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", dir=output_path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as temporary:
            temporary.write(payload)
        if output_path.exists() and not overwrite:
            raise ConversionError(f"Output file already exists: {output_path}")
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return output_path


def write_named_outputs(
    outputs: dict[str, bytes],
    output_dir: Path,
    overwrite: bool,
) -> list[Path]:
    """Stage and write a flat set of named files after complete preflight."""

    require(outputs, "There are no output files")
    output_dir = output_dir.resolve()
    if output_dir.exists():
        require(output_dir.is_dir(), f"Output path is not a directory: {output_dir}")
    else:
        output_dir.parent.mkdir(parents=True, exist_ok=True)

    names = sorted(outputs, key=lambda name: name.encode("utf-8"))
    for name in names:
        require(Path(name).name == name and name not in {"", ".", ".."}, f"Invalid output name: {name}")
    destinations = [output_dir / name for name in names]
    if not overwrite:
        existing = [path for path in destinations if path.exists()]
        if existing:
            raise ConversionError(f"Output file already exists: {existing[0]}")

    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    try:
        for name in names:
            (staging / name).write_bytes(outputs[name])

        if not output_dir.exists():
            os.replace(staging, output_dir)
        else:
            # All conversion and staging has succeeded before any destination
            # is changed.  Unrelated files already in the directory remain.
            for name in names:
                destination = output_dir / name
                if destination.exists() and not overwrite:
                    raise ConversionError(f"Output file already exists: {destination}")
                os.replace(staging / name, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destinations


def convert_mtn3_file(
    input_path: Path,
    output_path: Path,
    overwrite: bool = False,
) -> Path:
    """Convert one mtn3 file and write it to an explicit mtn2 path."""

    require(input_path.is_file(), f"Input file not found: {input_path}")
    require(input_path.suffix.lower() == ".mtn3", "Input extension must be .mtn3")
    require(output_path.suffix.lower() == ".mtn2", "Output extension must be .mtn2")
    require(
        input_path.resolve() != output_path.resolve(),
        "The input file itself cannot be used as the output path",
    )
    return write_single_output(convert_mtn3(input_path.read_bytes()), output_path, overwrite)


def convert_character_prm_file(
    input_path: Path,
    output_path: Path,
    overwrite: bool = False,
) -> Path:
    """Convert one character PRM and write it to an explicit PRM path."""

    require(input_path.is_file(), f"Input file not found: {input_path}")
    require(input_path.suffix.lower() == ".prm", "Input extension must be .prm")
    require(output_path.suffix.lower() == ".prm", "Output extension must be .prm")
    require(
        input_path.resolve() != output_path.resolve(),
        "The input file itself cannot be used as the output path",
    )
    return write_single_output(
        convert_character_prm(input_path.read_bytes()),
        output_path,
        overwrite,
    )


def convert_character_lkat_file(
    input_path: Path,
    output_path: Path,
    overwrite: bool = False,
) -> Path:
    """Convert one character LKAT and write it to an explicit LKAT path."""

    require(input_path.is_file(), f"Input file not found: {input_path}")
    require(input_path.suffix.lower() == ".lkat", "Input extension must be .lkat")
    require(output_path.suffix.lower() == ".lkat", "Output extension must be .lkat")
    require(
        input_path.resolve() != output_path.resolve(),
        "The input file itself cannot be used as the output path",
    )
    return write_single_output(
        convert_character_lkat(input_path.read_bytes()),
        output_path,
        overwrite,
    )


def convert_character_sil_file(
    input_path: Path,
    output_path: Path,
    overwrite: bool = False,
) -> Path:
    """Validate and copy one character SIL to an explicit SIL path."""

    require(input_path.is_file(), f"Input file not found: {input_path}")
    require(input_path.suffix.lower() == ".sil", "Input extension must be .sil")
    require(output_path.suffix.lower() == ".sil", "Output extension must be .sil")
    require(
        input_path.resolve() != output_path.resolve(),
        "The input file itself cannot be used as the output path",
    )
    return write_single_output(
        convert_character_sil(input_path.read_bytes()),
        output_path,
        overwrite,
    )


def convert_character_res_file(
    input_path: Path,
    output_path: Path,
    context_dir: Path | None = None,
    version: int = 1,
    overwrite: bool = False,
) -> Path:
    """Convert one RES.bin, using a sibling MTNINF2 when the RES needs it."""

    require(input_path.is_file(), f"Input file not found: {input_path}")
    require(
        input_path.resolve() != output_path.resolve(),
        "The input file itself cannot be used as the output path",
    )
    search_dir = context_dir if context_dir is not None else input_path.parent
    require(search_dir.is_dir(), f"Context directory not found: {search_dir}")
    matches = sorted(search_dir.glob("*.mtninf2"))
    require(len(matches) <= 1, f"Multiple .mtninf2 files found: {search_dir}")
    mtninf2_data = matches[0].read_bytes() if matches else None
    converted = convert_character_res(input_path.read_bytes(), mtninf2_data, version)
    return write_single_output(converted, output_path, overwrite)


def convert_p00_content_directory(
    source_dir: Path,
    output_dir: Path,
    overwrite: bool = False,
    res_version: int = 1,
) -> list[Path]:
    """Convert a complete extracted p00 model-content directory."""

    require(source_dir.is_dir(), f"Input directory not found: {source_dir}")
    require(
        source_dir.resolve() != output_dir.resolve(),
        "The input directory itself cannot be used as the output path",
    )
    outputs = build_p00_content_outputs(source_dir, res_version)
    return write_named_outputs(outputs, output_dir, overwrite)


def convert_p8_content_directory(
    source_dir: Path,
    output_dir: Path,
    overwrite: bool = False,
    res_version: int = 1,
) -> list[Path]:
    """Convert MTN, MTNINF, and RES and copy CMN from an extracted p80/p84 folder."""

    require(source_dir.is_dir(), f"Input directory not found: {source_dir}")
    require(
        source_dir.resolve() != output_dir.resolve(),
        "The input directory itself cannot be used as the output path",
    )
    outputs = build_p8_content_outputs(source_dir, res_version)
    return write_named_outputs(outputs, output_dir, overwrite)


def character_archive_slot(filename: str) -> str:
    """Return p00, p80, or p84 from a standard character XC filename."""

    path = Path(filename)
    require(path.suffix.lower() == ".xc", "Input extension must be .xc")
    stem = path.stem.lower()
    for slot in ("p00", "p80", "p84"):
        if stem.endswith("_" + slot):
            return slot
    raise ConversionError(f"Cannot determine p00/p80/p84 from the character XC filename: {filename}")


def convert_p00_xc_archive(archive: bytes, res_version: int = 1) -> bytes:
    """Convert one raw YW3 p00 XPCK archive entirely in memory."""

    source_files = unpack_xpck_archive(archive)
    converted_files = convert_p00_internal_files(source_files, res_version)
    return pack_xpck_files(converted_files)


def convert_p00_xc_file(
    input_path: Path,
    output_dir: Path,
    res_version: int = 1,
    overwrite: bool = False,
) -> Path:
    """Convert a raw p00 XC and preserve its filename in output_dir."""

    require(input_path.is_file(), f"Input XC not found: {input_path}")
    slot = character_archive_slot(input_path.name)
    require(slot == "p00", f"p00-xc cannot convert {slot}")
    resolved_output_dir = output_dir.resolve()
    if resolved_output_dir.exists():
        require(
            resolved_output_dir.is_dir(),
            f"XC output path is not a directory: {resolved_output_dir}",
        )
    destination = resolved_output_dir / input_path.name
    require(
        destination != input_path.resolve(),
        "Output cannot be written beside the input XC; specify a different output directory",
    )
    if destination.exists() and not overwrite:
        raise ConversionError(f"Output file already exists: {destination}")

    converted = convert_p00_xc_archive(input_path.read_bytes(), res_version)
    return write_single_output(converted, destination, overwrite)


def convert_p8_xc_archive(archive: bytes, res_version: int = 1) -> bytes:
    """Convert one raw YW3 p80/p84 XPCK archive entirely in memory."""

    source_files = unpack_xpck_archive(archive)
    converted_files = convert_p8_internal_files(source_files, res_version)
    return pack_xpck_files(converted_files)


def convert_p8_xc_file(
    input_path: Path,
    output_dir: Path,
    res_version: int = 1,
    overwrite: bool = False,
) -> Path:
    """Convert a raw p80/p84 XC and preserve its filename in output_dir."""

    require(input_path.is_file(), f"Input XC not found: {input_path}")
    slot = character_archive_slot(input_path.name)
    require(slot in {"p80", "p84"}, f"p8-xc cannot convert {slot}")
    resolved_output_dir = output_dir.resolve()
    if resolved_output_dir.exists():
        require(
            resolved_output_dir.is_dir(),
            f"XC output path is not a directory: {resolved_output_dir}",
        )
    destination = resolved_output_dir / input_path.name
    require(
        destination != input_path.resolve(),
        "Output cannot be written beside the input XC; specify a different output directory",
    )
    if destination.exists() and not overwrite:
        raise ConversionError(f"Output file already exists: {destination}")

    converted = convert_p8_xc_archive(input_path.read_bytes(), res_version)
    return write_single_output(converted, destination, overwrite)


CHARACTER_ARCHIVE_SLOTS = ("p00", "p80", "p84")


def _character_archive_base(filename: str) -> str:
    """Return the character prefix shared by one p00/p80/p84 archive trio."""

    slot = character_archive_slot(filename)
    stem = Path(filename).stem
    base = stem[: -(len(slot) + 1)]
    require(base, f"Character XC base name is empty: {filename}")
    return base


def convert_character_xc_archives(
    archives: dict[str, bytes],
    res_version: int = 1,
    *,
    copy_p00: bool = False,
) -> dict[str, bytes]:
    """Convert same-character XC files; optionally preserve p00 verbatim.

    Normal mode requires a complete trio and converts every archive. Explicit
    copy mode accepts the available slots only, validates the p00 container,
    and preserves its complete original bytes without internal conversion or
    repacking. Motion conversion errors are never suppressed.
    """

    require(res_version in {0, 1}, f"RES output version must be 0 or 1: {res_version}")
    if copy_p00:
        require(1 <= len(archives) <= 3,
                f"One to three XC archives (p00/p80/p84) are required in p00 copy mode (found: {len(archives)})")
    else:
        require(len(archives) == 3, f"Exactly three XC archives (p00/p80/p84) are required (found: {len(archives)})")
    by_slot: dict[str, tuple[str, bytes]] = {}
    bases: set[str] = set()
    for name, archive in archives.items():
        require(
            Path(name).name == name and name not in {"", ".", ".."},
            f"Unsafe XC filename: {name!r}",
        )
        slot = character_archive_slot(name)
        require(slot not in by_slot, f"Duplicate {slot} XC archive")
        by_slot[slot] = (name, archive)
        bases.add(_character_archive_base(name).casefold())

    missing = [slot for slot in CHARACTER_ARCHIVE_SLOTS if slot not in by_slot]
    require(copy_p00 or not missing, "Missing character XC archives: " + ", ".join(missing))
    require(len(bases) == 1, "Character base names do not match across p00/p80/p84")

    outputs: dict[str, bytes] = {}
    for slot in CHARACTER_ARCHIVE_SLOTS:
        if slot not in by_slot:
            continue
        name, archive = by_slot[slot]
        if slot == "p00":
            if copy_p00:
                # Validate the XPCK framing, filename CRCs and RES compression
                # only. Its internal resources need not pass p00 conversion.
                unpack_xpck_archive(archive)
                outputs[name] = archive
            else:
                outputs[name] = convert_p00_xc_archive(archive, res_version)
        else:
            outputs[name] = convert_p8_xc_archive(archive, res_version)
    return outputs


def find_character_xc_files(input_path: Path, *, allow_partial: bool = False) -> dict[str, Path]:
    """Resolve one character's XC paths, optionally permitting missing slots."""

    if input_path.is_file():
        require(input_path.suffix.lower() == ".xc", "Input file extension must be .xc")
        base = _character_archive_base(input_path.name)
        search_dir = input_path.parent
        selected_base = base.casefold()
    else:
        require(input_path.is_dir(), f"Input XC or directory not found: {input_path}")
        search_dir = input_path
        candidates = sorted(
            (path for path in search_dir.iterdir() if path.is_file() and path.suffix.lower() == ".xc"),
            key=lambda path: path.name.encode("utf-8"),
        )
        selected = []
        for path in candidates:
            try:
                character_archive_slot(path.name)
            except ConversionError:
                continue
            selected.append(path)
        candidates = selected
        require(candidates, f"Input directory contains no p00/p80/p84 XC archives: {search_dir}")
        bases: dict[str, str] = {}
        for path in candidates:
            base = _character_archive_base(path.name)
            bases.setdefault(base.casefold(), base)
        require(
            len(bases) == 1,
            "The input directory must contain XC archives for only one character "
            f"(base names found: {', '.join(sorted(bases.values()))})",
        )
        selected_base = next(iter(bases))

    resolved: dict[str, Path] = {}
    for path in search_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".xc":
            continue
        try:
            slot = character_archive_slot(path.name)
        except ConversionError:
            continue
        if _character_archive_base(path.name).casefold() != selected_base:
            continue
        require(slot not in resolved, f"Duplicate {slot} XC archive: {search_dir}")
        resolved[slot] = path

    missing = [slot for slot in CHARACTER_ARCHIVE_SLOTS if slot not in resolved]
    require(
        allow_partial or not missing,
        "XC archives for the same character are missing: " + ", ".join(missing),
    )
    return {slot: resolved[slot] for slot in CHARACTER_ARCHIVE_SLOTS if slot in resolved}


def convert_character_xc_set(
    input_path: Path,
    output_dir: Path,
    res_version: int = 1,
    overwrite: bool = False,
    *,
    copy_p00: bool = False,
) -> list[Path]:
    """Discover and atomically prepare one character's XC output set."""

    source_paths = find_character_xc_files(input_path, allow_partial=copy_p00)
    resolved_output_dir = output_dir.resolve()
    if resolved_output_dir.exists():
        require(
            resolved_output_dir.is_dir(),
            f"XC output path is not a directory: {resolved_output_dir}",
        )
    for source in source_paths.values():
        require(
            resolved_output_dir / source.name != source.resolve(),
            "Output cannot be written beside the input XC; specify a different output directory",
        )

    archives = {path.name: path.read_bytes() for path in source_paths.values()}
    converted = convert_character_xc_archives(archives, res_version, copy_p00=copy_p00)
    return write_named_outputs(converted, resolved_output_dir, overwrite)


def pack_xpck_file(
    input_dir: Path,
    output_path: Path,
    overwrite: bool = False,
) -> Path:
    """Pack one converted internal-file directory into an XC/XPCK file."""

    require(input_dir.is_dir(), f"Input directory not found: {input_dir}")
    require(output_path.suffix.lower() == ".xc", "Output extension must be .xc")
    resolved_input = input_dir.resolve()
    resolved_output = output_path.resolve()
    require(
        not resolved_output.is_relative_to(resolved_input),
        "XC output path must be outside the input directory",
    )
    archive = pack_xpck_directory(input_dir)
    return write_single_output(archive, output_path, overwrite)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert YW3 character resources to YWB1 format",
        epilog="Automatic shorthand: character_converter.py INPUT OUTPUT_DIRECTORY --auto [--copy-p00]. "
               "Without --copy-p00, all three XC files are required and converted.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    mtninf2 = subparsers.add_parser("mtninf2", help="Convert mtninf2 into individual mtninf files")
    mtninf2.add_argument("input", type=Path, help="YW3 .mtninf2 file")
    mtninf2.add_argument("output_dir", type=Path, help="Output directory for converted .mtninf files")
    mtninf2.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs with the same names")

    mtn3 = subparsers.add_parser("mtn3", help="Convert mtn3 to mtn2")
    mtn3.add_argument("input", type=Path, help="YW3 .mtn3 file")
    mtn3.add_argument("output", type=Path, help="Converted .mtn2 output file")
    mtn3.add_argument("--overwrite", action="store_true", help="Overwrite existing output")

    prm = subparsers.add_parser("prm", help="Convert a character PRM to YWB1 format")
    prm.add_argument("input", type=Path, help="YW3 .prm file")
    prm.add_argument("output", type=Path, help="Converted .prm output file")
    prm.add_argument("--overwrite", action="store_true", help="Overwrite existing output")

    lkat = subparsers.add_parser("lkat", help="Convert a character LKAT to YWB1 format")
    lkat.add_argument("input", type=Path, help="YW3 .lkat file")
    lkat.add_argument("output", type=Path, help="Converted .lkat output file")
    lkat.add_argument("--overwrite", action="store_true", help="Overwrite existing output")

    sil = subparsers.add_parser("sil", help="Validate and copy a character SIL")
    sil.add_argument("input", type=Path, help="YW3 .sil file")
    sil.add_argument("output", type=Path, help="Validated .sil output file")
    sil.add_argument("--overwrite", action="store_true", help="Overwrite existing output")

    res = subparsers.add_parser("res", help="Convert a character RES.bin to CHRC00/01")
    res.add_argument("input", type=Path, help="YW3 RES.bin")
    res.add_argument("output", type=Path, help="Converted RES.bin output file")
    res.add_argument(
        "--context-dir",
        type=Path,
        help="Directory to search for the matching .mtninf2 (default: parent of the input RES.bin)",
    )
    res.add_argument(
        "--res-version",
        type=int,
        choices=(0, 1),
        default=1,
        help="Output CHRC version (default: 1)",
    )
    res.add_argument("--overwrite", action="store_true", help="Overwrite existing output")

    p00_content = subparsers.add_parser(
        "p00-content",
        help="Convert all model files in an extracted p00 archive",
    )
    p00_content.add_argument("input_dir", type=Path, help="Directory containing extracted YW3 p00 files")
    p00_content.add_argument("output_dir", type=Path, help="Output directory for converted internal files")
    p00_content.add_argument(
        "--res-version",
        type=int,
        choices=(0, 1),
        default=1,
        help="Output CHRC version for RES.bin (default: 1)",
    )
    p00_content.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs with the same names")

    p8_content = subparsers.add_parser(
        "p8-content",
        help="Convert all MTN and MTNINF files in an extracted p80/p84 archive",
    )
    p8_content.add_argument("input_dir", type=Path, help="Directory containing extracted YW3 p80/p84 files")
    p8_content.add_argument("output_dir", type=Path, help="Output directory for converted internal files")
    p8_content.add_argument(
        "--res-version",
        type=int,
        choices=(0, 1),
        default=1,
        help="Output CHRC version for RES.bin (default: 1)",
    )
    p8_content.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs with the same names")

    pack_xc = subparsers.add_parser("pack-xc", help="Repack converted internal files as XC/XPCK")
    pack_xc.add_argument("input_dir", type=Path, help="Directory containing converted internal files")
    pack_xc.add_argument("output", type=Path, help="Output XC file")
    pack_xc.add_argument("--overwrite", action="store_true", help="Overwrite an existing XC file")

    p00_xc = subparsers.add_parser(
        "p00-xc",
        help="Extract, convert, and repack a raw YW3 p00 XC archive",
    )
    p00_xc.add_argument("input", type=Path, help="YW3 p00 XC archive")
    p00_xc.add_argument("output_dir", type=Path, help="Directory for the converted XC with the same filename")
    p00_xc.add_argument(
        "--res-version",
        type=int,
        choices=(0, 1),
        default=1,
        help="Output CHRC version for RES.bin (default: 1)",
    )
    p00_xc.add_argument("--overwrite", action="store_true", help="Overwrite an existing XC with the same name")

    p8_xc = subparsers.add_parser(
        "p8-xc",
        help="Extract, convert, and repack a raw YW3 p80/p84 XC archive",
    )
    p8_xc.add_argument("input", type=Path, help="YW3 p80 or p84 XC archive")
    p8_xc.add_argument("output_dir", type=Path, help="Directory for the converted XC with the same filename")
    p8_xc.add_argument(
        "--res-version",
        type=int,
        choices=(0, 1),
        default=1,
        help="Output CHRC version for RES.bin (default: 1)",
    )
    p8_xc.add_argument("--overwrite", action="store_true", help="Overwrite an existing XC with the same name")

    character_xc = subparsers.add_parser(
        "character-xc",
        help="Automatically convert the p00, p80, and p84 XC archives for one character",
    )
    character_xc.add_argument(
        "input",
        type=Path,
        help="Directory containing one character's p00/p80/p84 archives, or any one of them. "
             "All three are required unless --copy-p00 is specified; other XC slots are ignored.",
    )
    character_xc.add_argument("output_dir", type=Path, help="Directory for the output XC archives with the same filenames")
    character_xc.add_argument(
        "--res-version",
        type=int,
        choices=(0, 1),
        default=1,
        help="CHRC version for converted RES.bin files (default: 1); copied p00 is never modified",
    )
    character_xc.add_argument("--overwrite", action="store_true", help="Overwrite existing output XC archives with the same names")
    character_xc.add_argument(
        "--copy-p00",
        action="store_true",
        help="Copy p00 XC unchanged after container validation; convert available p80/p84 normally. "
             "Missing slots are allowed. No motion-error fallback.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    option_end = arguments.index("--") if "--" in arguments else len(arguments)
    auto_count = arguments[:option_end].count("--auto")
    if auto_count:
        if auto_count != 1:
            parser.error("--auto must be specified only once")
        arguments.remove("--auto")
        # Keep existing subcommands intact. The flag is an alias for just the
        # character-XC workflow, not for single-file/internal-file commands.
        subcommands = {"mtninf2", "mtn3", "prm", "lkat", "sil", "res", "p00-content",
                       "p8-content", "pack-xc", "p00-xc", "p8-xc", "character-xc"}
        if arguments and arguments[0] in subcommands:
            if arguments[0] != "character-xc":
                parser.error("--auto is only valid for character-xc conversion")
        else:
            arguments.insert(0, "character-xc")
    args = parser.parse_args(arguments)
    try:
        if args.command == "mtninf2":
            paths = convert_mtninf2_file(args.input, args.output_dir, args.overwrite)
            print(f"Conversion complete: wrote {len(paths)} mtninf files to {args.output_dir.resolve()}")
            return 0
        if args.command == "mtn3":
            path = convert_mtn3_file(args.input, args.output, args.overwrite)
            print(f"Conversion complete: {path}")
            return 0
        if args.command == "prm":
            path = convert_character_prm_file(args.input, args.output, args.overwrite)
            print(f"Conversion complete: {path}")
            return 0
        if args.command == "lkat":
            path = convert_character_lkat_file(args.input, args.output, args.overwrite)
            print(f"Conversion complete: {path}")
            return 0
        if args.command == "sil":
            path = convert_character_sil_file(args.input, args.output, args.overwrite)
            print(f"Validation and copy complete: {path}")
            return 0
        if args.command == "res":
            path = convert_character_res_file(
                args.input,
                args.output,
                args.context_dir,
                args.res_version,
                args.overwrite,
            )
            print(f"Conversion complete: {path} (CHRC0{args.res_version})")
            return 0
        if args.command == "p00-content":
            paths = convert_p00_content_directory(
                args.input_dir,
                args.output_dir,
                args.overwrite,
                args.res_version,
            )
            converted_count = sum(
                path.suffix.lower() in {".prm", ".lkat"} for path in paths
            )
            copied_count = sum(
                path.suffix.lower()
                in {".atr", ".cmn", ".mbn", ".mtr", ".sil", ".txp", ".xi"}
                for path in paths
            )
            print(
                "Conversion complete: "
                f"converted {converted_count} files, validated and copied {copied_count} files, "
                f"and wrote one RES file to {args.output_dir.resolve()}"
            )
            return 0
        if args.command == "p8-content":
            paths = convert_p8_content_directory(
                args.input_dir,
                args.output_dir,
                args.overwrite,
                args.res_version,
            )
            mtn2_count = sum(path.suffix.lower() == ".mtn2" for path in paths)
            mtninf_count = sum(path.suffix.lower() == ".mtninf" for path in paths)
            cmn_count = sum(path.suffix.lower() == ".cmn" for path in paths)
            res_count = sum(path.name.lower() == "res.bin" for path in paths)
            print(
                "Conversion complete: "
                f"wrote {mtn2_count} mtn2 files, {mtninf_count} mtninf files, "
                f"{cmn_count} copied cmn files, and {res_count} RES files "
                f"to {args.output_dir.resolve()}"
            )
            return 0
        if args.command == "pack-xc":
            path = pack_xpck_file(args.input_dir, args.output, args.overwrite)
            print(f"Repack complete: {path} ({path.stat().st_size} bytes)")
            return 0
        if args.command == "p00-xc":
            path = convert_p00_xc_file(
                args.input,
                args.output_dir,
                args.res_version,
                args.overwrite,
            )
            print(
                f"p00 automatic conversion complete: {args.input.resolve()} -> {path} "
                f"(CHRC0{args.res_version}, {path.stat().st_size} bytes)"
            )
            return 0
        if args.command == "p8-xc":
            path = convert_p8_xc_file(
                args.input,
                args.output_dir,
                args.res_version,
                args.overwrite,
            )
            print(
                f"Automatic conversion complete: {args.input.resolve()} -> {path} "
                f"(CHRC0{args.res_version}, {path.stat().st_size} bytes)"
            )
            return 0
        if args.command == "character-xc":
            paths = convert_character_xc_set(
                args.input,
                args.output_dir,
                args.res_version,
                args.overwrite,
                copy_p00=args.copy_p00,
            )
            if args.copy_p00:
                p00_present = any(character_archive_slot(path.name) == "p00" for path in paths)
                print(
                    "Automatic conversion complete (p00 copy mode): "
                    f"{', '.join(path.name for path in paths)} -> {args.output_dir.resolve()} "
                    f"(p00 {'copied unchanged' if p00_present else 'not present'}; "
                    f"available p80/p84 converted with CHRC0{args.res_version})"
                )
                return 0
            print(
                "Three-file automatic conversion complete: "
                f"{', '.join(path.name for path in paths)} -> {args.output_dir.resolve()} "
                f"(CHRC0{args.res_version})"
            )
            return 0
        raise ConversionError(f"Unsupported command: {args.command}")
    except (ConversionError, OSError) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
