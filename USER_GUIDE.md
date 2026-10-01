# YW3 to YWB1 Character XC Converter User Guide

## 1. About This Guide

This guide explains how to use `character_converter.py` to convert Yo-kai Watch 3 (YW3) character XC archives into a format usable by Yo-kai Watch Blasters (YWB1).

For normal use, the `character-xc` command is sufficient: it converts `p00`, `p80`, and `p84` together. Commands for individual archives and extracted internal files are primarily intended for research, validation, and isolating the cause of a problem.

Related documentation:

- [Binary-format analysis](./FORMAT_ANALYSIS.md)
- [Implementation specification](./IMPLEMENTATION_SPEC.md)

## 2. Requirements

- Python 3.10 or later.
- `character_convert/character_converter.py`.
- YW3 `p00`, `p80`, and `p84` XC archives for the same character, extracted from the ROM.
- A writable output directory.

No external Python packages are required.

On Windows, replace `python` at the beginning of each example with whichever command is available in your environment.

```text
python
py -3
Full path to the Python executable
```

The examples below assume PowerShell is running with the project root, `C:\ywb_mod`, as the current directory.

```powershell
Set-Location C:\ywb_mod
```

## 3. Preparing Input Files

Place one character's three XC archives in the same directory.

```text
input-directory/
├─ y473000_p00.xc
├─ y473000_p80.xc
└─ y473000_p84.xc
```

The input must satisfy these conditions:

- All three files have the same character base name.
- Their suffixes are `_p00.xc`, `_p80.xc`, and `_p84.xc`.
- All three are raw XC archives extracted from YW3.
- Input and output directories are different.

The existing `character_convert/yw3/y473000` sample has this layout.

```text
character_convert/yw3/y473000/
├─ y473000_p00.xc
├─ y473000_p80.xc
└─ y473000_p84.xc
```

The `*_content` directories beside those archives are not used by `character-xc`. The command extracts, converts, and repacks the raw XC entirely in memory.

## 4. Quick Start

### 4.1 Convert All Three Archives

The recommended command is:

```powershell
python .\character_convert\character_converter.py character-xc `
  ".\character_convert\yw3\y473000" `
  ".\character_convert\converted_character\y473000"
```

One-line form:

```powershell
python .\character_convert\character_converter.py character-xc ".\character_convert\yw3\y473000" ".\character_convert\converted_character\y473000"
```

On success, the output directory contains:

```text
character_convert/converted_character/y473000/
├─ y473000_p00.xc
├─ y473000_p80.xc
└─ y473000_p84.xc
```

The output filenames are identical to the input filenames.

### 4.2 Specify Any One of the Three Files

If all three archives are in the same directory, you may specify any one of them. The other two are discovered automatically.

```powershell
python .\character_convert\character_converter.py character-xc ".\character_convert\yw3\y473000\y473000_p00.xc" ".\character_convert\converted_character\y473000"
```

Specifying the `p80` or `p84` file produces the same result.

### 4.3 Success Message

The CLI prints a message in this form on success:

```text
Three-file automatic conversion complete: y473000_p00.xc, y473000_p80.xc, y473000_p84.xc -> <output> (CHRC01)
```

It means that automatic conversion of all three files completed successfully.

## 5. Selecting the RES Version

### 5.1 Default

Without an explicit option, every `RES.bin` is written as `CHRC01`.

```powershell
python .\character_convert\character_converter.py character-xc ".\character_convert\yw3\y473000" ".\character_convert\converted_character\y473000"
```

This is equivalent to:

```powershell
python .\character_convert\character_converter.py character-xc ".\character_convert\yw3\y473000" ".\character_convert\converted_character\y473000" --res-version 1
```

### 5.2 CHRC00

Specify `--res-version 0` only when `CHRC00` is required.

```powershell
python .\character_convert\character_converter.py character-xc ".\character_convert\yw3\y473000" ".\character_convert\converted_character\y473000_chrc00" --res-version 0
```

The selected version is applied to all three archives.

## 6. Overwriting Output

### 6.1 No Overwrite by Default

Conversion stops if a same-named output XC already exists. The current CLI error begins with:

```text
Error: Output file already exists: ...
```

Use another output directory when the existing result must be preserved.

### 6.2 Explicit Overwrite

Add `--overwrite` to replace the existing three XC files.

```powershell
python .\character_convert\character_converter.py character-xc ".\character_convert\yw3\y473000" ".\character_convert\converted_character\y473000" --overwrite
```

Unrelated files already present in the output directory are not deleted.

### 6.3 Overwrite with a RES Version

```powershell
python .\character_convert\character_converter.py character-xc ".\character_convert\yw3\y473000" ".\character_convert\converted_character\y473000" --res-version 0 --overwrite
```

Placing options after the positional arguments is the clearest form.

## 7. Checking the Result

### 7.1 Check the Files

Confirm that:

- All three `p00`, `p80`, and `p84` files were created.
- Their names match the input names.
- None of them is zero bytes long.
- No error message was printed.

PowerShell example:

```powershell
Get-ChildItem ".\character_convert\converted_character\y473000" -Filter "*.xc" | Select-Object Name, Length
```

### 7.2 Install into the Game

Place the converted XC archives at the corresponding same-name locations in the target ROM or mod environment. Always back up the original files elsewhere first.

Installation depends on the extraction, rebuilding, or mod tools being used, so this converter does not perform deployment automatically.

### 7.3 Recommended In-Game Test Order

Test in this order to make failures easier to isolate:

1. Install `p00` and inspect the model, textures, pose, and collision behavior.
2. Install `p80` and inspect animations used primarily in the Busters House.
3. Install `p84` and inspect battle and Medallium animations.
4. Install all three and verify the final configuration.

The complete automatic output has been validated in both an emulator and on real hardware. A new character may nevertheless contain a structure not present in the analyzed corpus.

## 8. Convert Only One XC

The three-file command is recommended for normal use. Per-slot conversion is useful for diagnosis.

### 8.1 p00

```powershell
python .\character_convert\character_converter.py p00-xc `
  ".\character_convert\yw3\y473000\y473000_p00.xc" `
  ".\character_convert\converted_single\y473000"
```

One-line form:

```powershell
python .\character_convert\character_converter.py p00-xc ".\character_convert\yw3\y473000\y473000_p00.xc" ".\character_convert\converted_single\y473000"
```

The input filename must end in `_p00.xc`.

### 8.2 p80

```powershell
python .\character_convert\character_converter.py p8-xc ".\character_convert\yw3\y473000\y473000_p80.xc" ".\character_convert\converted_single\y473000"
```

### 8.3 p84

```powershell
python .\character_convert\character_converter.py p8-xc ".\character_convert\yw3\y473000\y473000_p84.xc" ".\character_convert\converted_single\y473000"
```

`p8-xc` accepts only p80 or p84 and rejects p00.

### 8.4 Options

`p00-xc` and `p8-xc` support:

```text
--res-version 0
--res-version 1
--overwrite
```

## 9. Convert Extracted Internal Files

Use this workflow when you want to inspect internal-file output using an existing `*_content` directory.

### 9.1 Convert Complete p00 Contents

```powershell
python .\character_convert\character_converter.py p00-content `
  ".\character_convert\yw3\y473000\y473000_p00_content" `
  ".\character_convert\work\y473000_p00_converted"
```

One-line form:

```powershell
python .\character_convert\character_converter.py p00-content ".\character_convert\yw3\y473000\y473000_p00_content" ".\character_convert\work\y473000_p00_converted"
```

This command:

- Converts PRM.
- Converts LKAT.
- Validates and preserves ATR, CMN, MBN, MTR, SIL, TXP, and XI.
- Checks cross-file references against RES.
- Converts RES to CHRC00 or CHRC01.

### 9.2 Convert Complete p80 Contents

```powershell
python .\character_convert\character_converter.py p8-content ".\character_convert\yw3\y473000\y473000_p80_content" ".\character_convert\work\y473000_p80_converted"
```

### 9.3 Convert Complete p84 Contents

```powershell
python .\character_convert\character_converter.py p8-content ".\character_convert\yw3\y473000\y473000_p84_content" ".\character_convert\work\y473000_p84_converted"
```

`p8-content` performs the following operations:

- Converts one MTN3 to MTN2.
- Splits one MTNINF2 into multiple MTNINF files.
- Validates and preserves CMN files.
- Converts RES using names from MTNINF2.

### 9.4 Input Directory Requirements

- Internal files are directly under the directory.
- No subdirectories are present.
- The input directory itself is not used as the output directory.
- Numeric filenames form an unbroken sequence beginning at `000`.
- Unsupported extensions are not mixed into the directory.

## 10. Repack Converted Internal Files as XC

### 10.1 p00

```powershell
python .\character_convert\character_converter.py pack-xc `
  ".\character_convert\work\y473000_p00_converted" `
  ".\character_convert\work\y473000_p00.xc"
```

### 10.2 p80

```powershell
python .\character_convert\character_converter.py pack-xc ".\character_convert\work\y473000_p80_converted" ".\character_convert\work\y473000_p80.xc"
```

### 10.3 p84

```powershell
python .\character_convert\character_converter.py pack-xc ".\character_convert\work\y473000_p84_converted" ".\character_convert\work\y473000_p84.xc"
```

### 10.4 Repacking Requirements

- The output extension is `.xc`.
- The input is a flat directory of internal files.
- `RES.bin` exists and is uncompressed `CHRC00` or `CHRC01`.
- No YW3-generation `.mtn3`, `.mtninf2`, or related file remains.
- The output XC is not placed inside the input internal-file directory.

After packing, the converter extracts the new XC again and verifies that the resulting internal-file set exactly matches the input set.

## 11. Convert Individual Internal Files

### 11.1 MTN3 to MTN2

```powershell
python .\character_convert\character_converter.py mtn3 `
  ".\character_convert\yw3\y473000\y473000_p80_content\000.mtn3" `
  ".\character_convert\work\000.mtn2"
```

The output extension must be `.mtn2`.

### 11.2 MTNINF2 to Multiple MTNINF Files

```powershell
python .\character_convert\character_converter.py mtninf2 `
  ".\character_convert\yw3\y473000\y473000_p80_content\000.mtninf2" `
  ".\character_convert\work\y473000_p80_mtninf"
```

Output uses sequential names.

```text
000.mtninf
001.mtninf
002.mtninf
...
```

### 11.3 PRM

```powershell
python .\character_convert\character_converter.py prm `
  ".\character_convert\yw3\y473000\y473000_p00_content\000.prm" `
  ".\character_convert\work\000.prm"
```

The input and output cannot be the same file.

### 11.4 LKAT

```powershell
python .\character_convert\character_converter.py lkat `
  ".\character_convert\yw3\y473000\y473000_p00_content\000.lkat" `
  ".\character_convert\work\000.lkat"
```

### 11.5 Validated SIL Copy

```powershell
python .\character_convert\character_converter.py sil `
  ".\character_convert\yw3\y473000\y473000_p00_content\000.sil" `
  ".\character_convert\work\000.sil"
```

SIL content is not transformed. The converter validates its XCSL/CMBC structure and writes the same bytes.

### 11.6 RES.bin

p00 example:

```powershell
python .\character_convert\character_converter.py res `
  ".\character_convert\yw3\y473000\y473000_p00_content\RES.bin" `
  ".\character_convert\work\p00_RES.bin"
```

p80 and p84 RES conversion needs a context directory in which to locate the corresponding MTNINF2. The option can be omitted when RES and MTNINF2 are already in the same directory.

```powershell
python .\character_convert\character_converter.py res `
  ".\character_convert\yw3\y473000\y473000_p80_content\RES.bin" `
  ".\character_convert\work\p80_RES.bin"
```

To use MTNINF2 from another location:

```powershell
python .\character_convert\character_converter.py res `
  ".\somewhere\RES.bin" `
  ".\character_convert\work\RES.bin" `
  --context-dir ".\somewhere\matching_p80_content"
```

Multiple `.mtninf2` files in the context directory are ambiguous and cause an error.

## 12. Display Help

All commands:

```powershell
python .\character_convert\character_converter.py --help
```

Individual commands:

```powershell
python .\character_convert\character_converter.py character-xc --help
python .\character_convert\character_converter.py p00-xc --help
python .\character_convert\character_converter.py p8-xc --help
python .\character_convert\character_converter.py p00-content --help
python .\character_convert\character_converter.py p8-content --help
python .\character_convert\character_converter.py pack-xc --help
```

## 13. Troubleshooting

The converter uses the following English error-message fragments. Each item explains the likely cause and corrective action.

### 13.1 `Input XC or directory not found`

- Check the path spelling.
- Quote paths containing spaces.
- Confirm that the current directory is `C:\ywb_mod`.

```powershell
Get-Location
```

### 13.2 `XC archives for the same character are missing`

Confirm that p00, p80, and p84 with the same base name are all present beside the selected input file.

### 13.3 `Character base names do not match across p00/p80/p84`

XC archives from different characters have been mixed. Use three files belonging to the same character.

### 13.4 `The input directory must contain XC archives for only one character`

The directory contains XC archives for multiple characters. Separate them by character, or specify one member of the desired three-file set directly.

### 13.5 `Output file already exists`

Use another output directory, or inspect the current output and add `--overwrite` only when replacement is intended.

### 13.6 `Output cannot be written beside the input XC`

The converter protects the source by rejecting the same path and name as output. Select another output directory.

### 13.7 `The PRM may already be converted`

The input may already be in YWB1 format or may not match the analyzed YW3 character PRM layout. Use the original YW3 PRM or XC.

### 13.8 `RES section 0x0191 conversion requires the .mtninf2 from the same p80/p84 archive`

A p80/p84 RES is being converted without its corresponding MTNINF2. Place the MTNINF2 beside the input RES or specify `--context-dir`.

### 13.9 Messages Containing `Unsupported`, `unknown`, or `not one of the verified values`

The file is not necessarily corrupt; it may contain a legitimate new structure absent from the current sample corpus.

Preserve the following information:

- Complete error message.
- Input XC filename.
- Command that produced the error.
- Corresponding YWB1 XC for the same character, if available.

Do not delete the validation or manually zero the value. Treat it as a new format requiring analysis.

### 13.10 Python Is Not Found

Try:

```powershell
py -3 --version
```

If that command is also unavailable, install or otherwise provide Python 3.10 or later and invoke the script using the full path to the Python executable.

## 14. When Output Does Not Match Official YWB1 Bytes

A byte difference is not necessarily a failure.

- MTN2 compression choices can differ from the official file.
- PRM conversion preserves YW3 model content instead of reproducing official YWB1 vertex rounding.
- Official YWB1 versions of MTR, MBN, XI, and CMN can contain content revisions.

The converter changes structures required for YWB1 compatibility while preserving unrelated YW3 asset content. Judge success using decompressed structure and in-game behavior rather than only the compressed whole-file bytes.

## 15. Safe Operating Procedure

1. Store the XC archives extracted from the ROM in a read-only backup.
2. Use a separate input directory for each character.
3. Write output to a directory separate from input.
4. Do not use `--overwrite` for the first conversion.
5. Confirm the names and sizes of all three output files.
6. Back up the original YWB1 archives before installing replacements.
7. Begin testing with only one character.
8. Test p00, p80, and p84 individually in that order.
9. If a problem occurs, isolate it in this order: one XC, extracted contents, then one internal format.

## 16. Command Reference

### Normal Three-Archive Conversion

```powershell
python .\character_convert\character_converter.py character-xc <input-directory-or-one-XC> <output-directory>
```

### Three Archives with CHRC00

```powershell
python .\character_convert\character_converter.py character-xc <input> <output-directory> --res-version 0
```

### Overwrite

```powershell
python .\character_convert\character_converter.py character-xc <input> <output-directory> --overwrite
```

### p00 Only

```powershell
python .\character_convert\character_converter.py p00-xc <p00.xc> <output-directory>
```

### p80 or p84 Only

```powershell
python .\character_convert\character_converter.py p8-xc <p80.xc-or-p84.xc> <output-directory>
```

### Extracted p00

```powershell
python .\character_convert\character_converter.py p00-content <input-content-directory> <output-content-directory>
```

### Extracted p80 or p84

```powershell
python .\character_convert\character_converter.py p8-content <input-content-directory> <output-content-directory>
```

### Repack as XC

```powershell
python .\character_convert\character_converter.py pack-xc <converted-content-directory> <output.xc>
```

## 17. Recommended Normal Workflow

Use the following sequence for a new character.

```text
1. Extract the p00, p80, and p84 XC archives from the YW3 ROM.
2. Place one character's three files in the same input directory.
3. Run character-xc using the default CHRC01 output.
4. Confirm that all three output XC archives exist.
5. Back up the original YWB1 XC archives.
6. Install and test p00, p80, and p84 incrementally.
7. If each succeeds, install all three as the final set.
```

The standard one-line command is:

```powershell
python .\character_convert\character_converter.py character-xc ".\character_convert\yw3\y473000" ".\character_convert\converted_character\y473000"
```
