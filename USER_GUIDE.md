# YW3 to YWB1 Character XC Converter User Guide

## 1. About This Guide

This guide explains how to use `character_converter.py` to convert Yo-kai Watch 3 (YW3) character XC archives into a format usable by Yo-kai Watch Blasters (YWB1).

For normal strict conversion, `character-xc` converts `p00`, `p80`, and `p84` together. The shorter `INPUT OUTPUT --auto` form selects the same operation. An explicit `--copy-p00` mode instead preserves the original p00 XC bytes and converts only the available p80/p84 files; it also permits incomplete major-slot sets. These modes have different validation guarantees, explained below.

Related documentation:

- [Binary-format analysis](./FORMAT_ANALYSIS.md)
- [Implementation specification](./IMPLEMENTATION_SPEC.md)

## 2. Requirements

- Python 3.10 or later.
- `character_converter.py`.
- YW3 character XC archives extracted from the ROM: a same-character p00/p80/p84 trio for default strict mode, or at least one of those slots for explicit `--copy-p00` mode.
- A writable output directory.

No external Python packages are required.

On Windows, replace `python` at the beginning of each example with whichever command is available in your environment.

```text
python
py -3
Full path to the Python executable
```

Run the examples from the cloned or extracted repository directory: the folder containing `character_converter.py`. You can keep that folder anywhere on your computer; no developer-specific workspace path is required.

```powershell
python character_converter.py --help
```

All input and output paths below are relative to that repository directory. The commands are PowerShell examples; on other systems, use the equivalent paths for your shell. Input files, extracted contents, ROMs, and test fixtures are **not included** in the public release. Prepare your own legally obtained files before running the conversion examples.

## 3. Preparing Input Files

Place one character's available major XC archives in the same directory. Default strict conversion requires all three:

```text
input/y473000/
├─ y473000_p00.xc
├─ y473000_p80.xc
└─ y473000_p84.xc
```

The input must satisfy these conditions:

- All selected files have the same character base name.
- Their suffixes are `_p00.xc`, `_p80.xc`, and `_p84.xc`.
- The files are raw XC archives extracted from YW3.
- Input and output directories are different.

For example, create an `input/y473000` directory beside the script and add your own extracted files. A possible local layout is:

```text
repository-root/
├─ character_converter.py
└─ input/
   └─ y473000/
      ├─ y473000_p00.xc
      ├─ y473000_p80.xc
      └─ y473000_p84.xc
```

Your input directory may also contain other slots such as p10/p20. Both normal and copy modes ignore non-major XC slots. You may select the directory or any one p00/p80/p84 file. Directory input still rejects major XCs belonging to different character base names; selecting one major file restricts discovery to that character's major siblings. A dedicated directory per character is the clearest arrangement.

No game samples are distributed with the converter. Paths in extracted-content examples below are illustrative locations you must prepare yourself. `*_content` directories are not used by the raw-XC commands.

## 4. Quick Start

### 4.1 Convert All Three Archives

The recommended command is:

```powershell
python character_converter.py `
  ".\input\y473000\y473000_p00.xc" `
  ".\converted\y473000" --auto
```

One-line form:

```powershell
python character_converter.py ".\input\y473000\y473000_p00.xc" ".\converted\y473000" --auto
```

On success, the output directory contains:

```text
converted/y473000/
├─ y473000_p00.xc
├─ y473000_p80.xc
└─ y473000_p84.xc
```

The output filenames are identical to the input filenames.

### 4.2 Specify Any One of the Three Files

If all three archives are in the same directory, you may specify any one of them. The other two are discovered automatically.

```powershell
python character_converter.py character-xc ".\input\y473000\y473000_p00.xc" ".\converted\y473000"
```

Specifying the `p80` or `p84` file produces the same result.

Directory input is also valid even when that one-character ROM directory contains other slots:

```powershell
python character_converter.py ".\input\y473000" ".\converted\y473000" --auto
```

### 4.3 Success Message

The CLI prints a message in this form on success:

```text
Three-file automatic conversion complete: y473000_p00.xc, y473000_p80.xc, y473000_p84.xc -> <output> (CHRC01)
```

It means that automatic conversion of all three files completed successfully.

### 4.4 Short Form Versus Subcommand Form

These forms are equivalent:

```powershell
python character_converter.py INPUT OUTPUT_DIRECTORY --auto
python character_converter.py character-xc INPUT OUTPUT_DIRECTORY
```

`--auto` is the selector for the form without a subcommand; it does not mean recursively convert every character in a ROM tree. With the explicit `character-xc` subcommand it is redundant and may be omitted; other subcommands cannot use it. Without `--copy-p00`, both forms retain strict three-file conversion, including p00 internal-format checks and RES rebuilding.

### 4.5 Explicit p00 Copy Mode

To retain the source p00 unchanged while converting the available motion slots:

```powershell
python character_converter.py ".\input\y473000\y473000_p00.xc" ".\converted\y473000_copy_p00" --auto --copy-p00
```

Equivalent long form:

```powershell
python character_converter.py character-xc ".\input\y473000\y473000_p00.xc" ".\converted\y473000_copy_p00" --copy-p00
```

| Behavior | Default strict mode | Explicit `--copy-p00` |
|---|---|---|
| Selected major files | Exactly p00, p80, and p84 required | Any existing same-character subset of 1–3 major files |
| p00 when present | Validate and convert internal formats, rebuild RES and XPCK | Validate XPCK container, then copy the entire original XC byte-for-byte |
| p80/p84 when present | Normal conversion and repack | The same normal conversion and repack |
| Missing major slots | Error | Not generated or substituted |
| RES version option | Applied to all converted slots | Applied only to converted p80/p84; copied p00 keeps its original RES |

The flag is an **always-copy selection**, not an automatic fallback after p00 conversion fails. Even a p00 that strict mode could convert is copied unchanged when this flag is present. The copied p00 is not rebuilt, renamed internally, or assigned CHRC01/00; its source RES can remain CHRC02. Internal PRM/XI/MBN/RES references are not model-validated in this mode.

The project author reports that unmodified YW3 p00 resources can work in B1. This is author-provided runtime evidence, not new game verification by this tool, and not proof that every copied model is compatible. Check model appearance, textures, attachments, and behavior in game.

All selected files are checked/prepared before output starts. If a copied p00 has an invalid XPCK container, or any selected p80/p84 fails conversion, no new selected outputs are written. Existing output files remain unchanged by that format failure. The flag never copies an unsupported motion file as a fallback.

A complete-trio copy-mode success message has this form:

```text
Automatic conversion complete (p00 copy mode): y473000_p00.xc, y473000_p80.xc, y473000_p84.xc -> <output> (p00 copied unchanged; available p80/p84 converted with CHRC01)
```

The file list can be shorter for partial input; when p00 is absent, the message says `p00 not present`. `CHRC01` in this message refers to converted motion files, never to the copied p00.

### 4.6 Incomplete Major-Slot Sets

`--copy-p00` also permits a partial input set. Select any existing major XC file, or a directory containing major XCs of only one character.

- Only p00 exists: output is one exact copy of p00 after container validation.
- p00 and p80 exist: copy p00 and normally convert p80; do not create p84.
- p00 is absent: normally convert whichever p80/p84 files exist; do not create p00.
- No p00/p80/p84 exists: error; non-major slots are not substitutes.

Example using a prepared p00-only input directory:

```powershell
python character_converter.py ".\input\x671000\x671000_p00.xc" ".\converted\x671000" --auto --copy-p00
```

This example requires you to prepare that input file; it is not a bundled sample. In default mode, the same incomplete input still fails. Individual `p8-xc` commands remain available for separately converting one motion XC.

## 5. Selecting the RES Version

### 5.1 Default

Without an explicit option, every **converted** `RES.bin` is written as `CHRC01`. A p00 copied with `--copy-p00` is never rewritten, so it retains its source RES version.

```powershell
python character_converter.py ".\input\y473000\y473000_p00.xc" ".\converted\y473000" --auto
```

This is equivalent to:

```powershell
python character_converter.py ".\input\y473000\y473000_p00.xc" ".\converted\y473000" --auto --res-version 1
```

### 5.2 CHRC00

Specify `--res-version 0` only when `CHRC00` is required.

```powershell
python character_converter.py ".\input\y473000\y473000_p00.xc" ".\converted\y473000_chrc00" --auto --res-version 0
```

In strict mode the selected version is applied to all three archives. With `--copy-p00`, it affects only the converted p80/p84 files. If only p00 exists in copy mode, no RES is rewritten at all.

## 6. Overwriting Output

### 6.1 No Overwrite by Default

Conversion stops if a same-named output XC already exists. The current CLI error begins with:

```text
Error: Output file already exists: ...
```

Use another output directory when the existing result must be preserved.

### 6.2 Explicit Overwrite

Add `--overwrite` to replace existing same-named selected XC files: three in strict mode, or the available 1–3 files in copy mode.

```powershell
python character_converter.py ".\input\y473000\y473000_p00.xc" ".\converted\y473000" --auto --overwrite
```

Unrelated files already present in the output directory are not deleted.

Format validation and staging finish before any final output is replaced. However, replacing multiple files inside an existing output directory is not a filesystem transaction: an OS-level failure midway through replacement cannot be rolled back automatically. Keep an external backup when overwriting important results.

### 6.3 Overwrite with a RES Version

```powershell
python character_converter.py ".\input\y473000\y473000_p00.xc" ".\converted\y473000" --auto --res-version 0 --overwrite
```

Placing options after the positional arguments is the clearest form.

## 7. Checking the Result

### 7.1 Check the Files

Confirm that:

- In strict mode, all three `p00`, `p80`, and `p84` files were created. In copy mode, each selected existing major slot was written and missing slots were not invented.
- Their names match the input names.
- None of them is zero bytes long.
- No error message was printed.

PowerShell example:

```powershell
Get-ChildItem ".\converted\y473000" -Filter "*.xc" | Select-Object Name, Length
```

For a p00 copy, matching SHA-256 values confirm byte identity:

```powershell
Get-FileHash ".\input\y473000\y473000_p00.xc" -Algorithm SHA256
Get-FileHash ".\converted\y473000_copy_p00\y473000_p00.xc" -Algorithm SHA256
```

### 7.2 Install into the Game

Place the converted XC archives at the corresponding same-name locations in the target ROM or mod environment. Always back up the original files elsewhere first.

Installation depends on the extraction, rebuilding, or mod tools being used, so this converter does not perform deployment automatically.

### 7.3 Recommended In-Game Test Order

Test in this order to make failures easier to isolate:

1. Install `p00` and inspect the model, textures, pose, and collision behavior.
2. Install `p80` and inspect animations used primarily in the Busters House.
3. Install `p84` and inspect battle and Medallium animations.
4. Install all selected files and verify the final configuration; skip absent slots when intentionally testing a partial copy-mode set.

The original strictly converted sample sets were validated in an emulator and on real hardware. The later full-corpus variants have structural checks, not new game confirmation. The p00-copy option is based on the project author's report about unchanged p00 behavior; test each selected character rather than treating the copy operation as a model-compatibility guarantee.

## 8. Convert Only One XC

The three-file command is recommended for normal use. Per-slot conversion is useful for diagnosis.

### 8.1 p00

```powershell
python character_converter.py p00-xc `
  ".\input\y473000\y473000_p00.xc" `
  ".\converted\single\y473000"
```

One-line form:

```powershell
python character_converter.py p00-xc ".\input\y473000\y473000_p00.xc" ".\converted\single\y473000"
```

The input filename must end in `_p00.xc`.

### 8.2 p80

```powershell
python character_converter.py p8-xc ".\input\y473000\y473000_p80.xc" ".\converted\single\y473000"
```

### 8.3 p84

```powershell
python character_converter.py p8-xc ".\input\y473000\y473000_p84.xc" ".\converted\single\y473000"
```

`p8-xc` accepts only p80 or p84 and rejects p00.

### 8.4 Options

`p00-xc` and `p8-xc` support:

```text
--res-version 0
--res-version 1
--overwrite
```

`--copy-p00` belongs to `character-xc` and the short `--auto` form, not to `p00-xc`, `p8-xc`, or extracted-content commands. Use the copy mode in Section 4 even when only a p00 exists.

## 9. Convert Extracted Internal Files

Use this workflow when you want to inspect internal-file output using a `*_content` directory that **you have extracted yourself**. The converter does not ship those directories or create them persistently when converting raw XC. For the examples below, place your extracted sets under `input/y473000/y473000_p00_content`, `..._p80_content`, or `..._p84_content`; output is kept separately under `converted/work`.

### 9.1 Convert Complete p00 Contents

```powershell
python character_converter.py p00-content `
  ".\input\y473000\y473000_p00_content" `
  ".\converted\work\y473000_p00_converted"
```

One-line form:

```powershell
python character_converter.py p00-content ".\input\y473000\y473000_p00_content" ".\converted\work\y473000_p00_converted"
```

This command:

- Converts PRM.
- Converts LKAT.
- Validates and preserves ATR, CMN, MBN, MTR, SIL, TXP, and XI.
- Checks cross-file references against RES.
- Converts RES to CHRC00 or CHRC01.

### 9.2 Convert Complete p80 Contents

```powershell
python character_converter.py p8-content ".\input\y473000\y473000_p80_content" ".\converted\work\y473000_p80_converted"
```

### 9.3 Convert Complete p84 Contents

```powershell
python character_converter.py p8-content ".\input\y473000\y473000_p84_content" ".\converted\work\y473000_p84_converted"
```

`p8-content` performs the following operations:

- Converts each supported MTN3/MTM3/IMM3 bundle into one or more numbered generation-2 animations.
- Splits supported MTNINF2/MTMINF2/IMMINF2 information into individual old-format INF files.
- Validates and preserves already-old animation/INF files when present.
- Processes optional CMN, LKAT, and SIL using their known rules.
- Rebuilds all present RES animation/INF categories using actual logical identities.

### 9.4 Input Directory Requirements

- Internal files are directly under the directory.
- No subdirectories are present.
- The input directory itself is not used as the output directory.
- Numeric filenames form an unbroken sequence beginning at `000`.
- Unsupported extensions are not mixed into the directory.

## 10. Repack Converted Internal Files as XC

### 10.1 p00

```powershell
python character_converter.py pack-xc `
  ".\converted\work\y473000_p00_converted" `
  ".\converted\work\y473000_p00.xc"
```

### 10.2 p80

```powershell
python character_converter.py pack-xc ".\converted\work\y473000_p80_converted" ".\converted\work\y473000_p80.xc"
```

### 10.3 p84

```powershell
python character_converter.py pack-xc ".\converted\work\y473000_p84_converted" ".\converted\work\y473000_p84.xc"
```

### 10.4 Repacking Requirements

- The output extension is `.xc`.
- The input is a flat directory of internal files.
- `RES.bin` exists and is uncompressed `CHRC00` or `CHRC01`.
- No YW3-generation `.mtn3`, `.mtninf2`, or related file remains.
- The output XC is not placed inside the input internal-file directory.

After packing, the converter extracts the new XC again and verifies that the resulting internal-file set exactly matches the input set.

An unchanged p00 from `--copy-p00` is not created with `pack-xc`: the entire original XC is copied directly. Its retained CHRC02 is intentional and is not a reason to rewrite its internals just to satisfy this separate packer's old-RES precondition.

## 11. Convert Individual Internal Files

### 11.1 MTN3 to MTN2

```powershell
python character_converter.py mtn3 `
  ".\input\y473000\y473000_p80_content\000.mtn3" `
  ".\converted\work\000.mtn2"
```

The output extension must be `.mtn2`.

The standalone `mtn3` command retains its single-output contract. A bundle containing multiple logical MTN entries must use `p8-content`, `p8-xc`, or automatic character conversion so each entry receives its own numbered output.

### 11.2 MTNINF2 to Multiple MTNINF Files

```powershell
python character_converter.py mtninf2 `
  ".\input\y473000\y473000_p80_content\000.mtninf2" `
  ".\converted\work\y473000_p80_mtninf"
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
python character_converter.py prm `
  ".\input\y473000\y473000_p00_content\000.prm" `
  ".\converted\work\000.prm"
```

The input and output cannot be the same file.

### 11.4 LKAT

```powershell
python character_converter.py lkat `
  ".\input\y473000\y473000_p00_content\000.lkat" `
  ".\converted\work\000.lkat"
```

### 11.5 Validated SIL Copy

```powershell
python character_converter.py sil `
  ".\input\y473000\y473000_p00_content\000.sil" `
  ".\converted\work\000.sil"
```

SIL content is not transformed. The converter validates its XCSL/CMBC structure and writes the same bytes.

### 11.6 RES.bin

p00 example:

The standalone `res` command rebuilds only RES, not its companion resources or the complete cross-file graph. Use `p00-content`/`p00-xc` or the automatic character workflow when you need full model validation.

```powershell
python character_converter.py res `
  ".\input\y473000\y473000_p00_content\RES.bin" `
  ".\converted\work\p00_RES.bin"
```

p80 and p84 RES conversion needs a context directory in which to locate the corresponding MTNINF2. The option can be omitted when RES and MTNINF2 are already in the same directory.

This standalone command retains the original single-MTN-root `out_00` compatibility rule and discovers only `.mtninf2` context. It is **not** the complete category-aware path for multiple roots, non-`out_00` root identities, MTM, or IMM. Use `p8-content`, `p8-xc`, or automatic character conversion for those cases. Changing RES alone is not equivalent to converting the complete XC.

```powershell
python character_converter.py res `
  ".\input\y473000\y473000_p80_content\RES.bin" `
  ".\converted\work\p80_RES.bin"
```

To use MTNINF2 from another location:

```powershell
python character_converter.py res `
  ".\somewhere\RES.bin" `
  ".\converted\work\RES.bin" `
  --context-dir ".\somewhere\matching_p80_content"
```

Multiple `.mtninf2` files in the context directory are ambiguous and cause an error.

## 12. Display Help

All commands:

```powershell
python character_converter.py --help
```

Individual commands:

```powershell
python character_converter.py character-xc --help
python character_converter.py p00-xc --help
python character_converter.py p8-xc --help
python character_converter.py p00-content --help
python character_converter.py p8-content --help
python character_converter.py pack-xc --help
```

## 13. Troubleshooting

The converter uses the following English error-message fragments. Each item explains the likely cause and corrective action.

### 13.1 `Input XC or directory not found`

- Check the path spelling.
- Quote paths containing spaces.
- Confirm that the current directory contains the release's `character_converter.py` and that your paths point to files you supplied yourself.

```powershell
Get-Location
```

### 13.2 `XC archives for the same character are missing`

Confirm that p00, p80, and p84 with the same base name are all present beside the selected input file.

This is required in default strict mode. Explicit `--copy-p00` permits a partial major-slot set; it still requires at least one major XC and matching base names. It does not invent the missing files.

### 13.3 `Character base names do not match across p00/p80/p84`

XC archives from different characters have been mixed. Use only major files belonging to one character; default strict mode requires all three.

### 13.4 `The input directory must contain XC archives for only one character`

The directory contains XC archives for multiple characters. Separate them by character, or specify one member of the desired three-file set directly.

Directory input ignores p10/p20 and other non-major XC slots in both modes. It still rejects a mixture of major character base names. Selecting one major XC file restricts discovery to the selected character.

### 13.5 `Output file already exists`

Use another output directory, or inspect the current output and add `--overwrite` only when replacement is intended.

### 13.6 `Output cannot be written beside the input XC`

The converter protects the source by rejecting the same path and name as output. Select another output directory.

### 13.7 `the PRM may already be converted`

Known old PRMs with the verified `0x44` block and marker are accepted unchanged. This error is for a block length outside the supported old/new layouts, not a blanket rejection of every already-converted PRM. Use the original source file and retain the full message when requesting analysis of an unknown layout.

### 13.8 `RES .mtninf2 conversion requires exactly one bundle from the same archive`

A p80/p84 RES is being converted without its corresponding MTNINF2. Place the MTNINF2 beside the input RES or specify `--context-dir`.

### 13.9 Messages Containing `Unsupported`, `unknown`, or `not one of the verified values`

The file is not necessarily corrupt; it may contain a legitimate new structure absent from the current sample corpus.

Preserve the following information:

- Complete error message.
- Input XC filename.
- Command that produced the error.
- Corresponding YWB1 XC for the same character, if available.

Do not delete the validation or manually zero the value. Treat it as a new format requiring analysis.

An unsupported **p00 internal conversion** is not proof that an unchanged p00 cannot run in B1. You can explicitly select `--copy-p00` to preserve that archive with container-only validation and perform your own game test. This option does not fix its unknown internal conversion rule or permit an unsupported p80/p84.

### 13.10 Python Is Not Found

Try:

```powershell
py -3 --version
```

If that command is also unavailable, install or otherwise provide Python 3.10 or later and invoke the script using the full path to the Python executable.

### 13.11 Two Motion Archives That Still Cannot Be Converted

| XC filename | Problem internal file | Unsupported form |
|---|---|---|
| `x611000_p80.xc` | `000.mtninf2` | Entry 2, descriptor 0: A=4, event `0x044E`, auxiliary value 0 |
| `x791000_p84.xc` | `000.mtninf2` | Entry 5, descriptor 0: A=16 |

`--copy-p00` does not bypass either error. Selected p80/p84 archives always use normal conversion; they are never copied or stripped as a fallback. If one of these archives is selected, the set operation fails before writing any new selected output. Use `p8-xc` only to test a different available motion archive independently, not to force these unknown forms through.

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
5. Confirm names and sizes of all selected outputs; if copying p00, compare its input/output hash.
6. Back up the original YWB1 archives before installing replacements.
7. Begin testing with only one character.
8. Test p00, p80, and p84 individually in that order.
9. If a problem occurs, isolate it in this order: one XC, extracted contents, then one internal format.

## 16. Command Reference

Angle-bracketed arguments in this reference are placeholders, not literal PowerShell syntax. Replace each placeholder with your own path and omit the angle brackets; quote paths containing spaces. The ready-to-adapt commands in Section 4 use the illustrative `input/<character>` and `converted/<character>` layout.

### Normal Three-Archive Conversion

```powershell
python character_converter.py character-xc <input-directory-or-one-XC> <output-directory>
```

### Equivalent Short Form

```powershell
python character_converter.py <input-directory-or-one-XC> <output-directory> --auto
```

### Preserve p00 and Convert Available Motion Slots

```powershell
python character_converter.py <input-directory-or-one-major-XC> <output-directory> --auto --copy-p00
```

The selected set may contain 1–3 same-character major files. Missing slots remain absent. To replace existing selected outputs, add `--overwrite`; source protection remains in force.

### Three Archives with CHRC00

```powershell
python character_converter.py character-xc <input> <output-directory> --res-version 0
```

### Overwrite

```powershell
python character_converter.py character-xc <input> <output-directory> --overwrite
```

### p00 Only

```powershell
python character_converter.py p00-xc <p00.xc> <output-directory>
```

### p80 or p84 Only

```powershell
python character_converter.py p8-xc <p80.xc-or-p84.xc> <output-directory>
```

### Extracted p00

```powershell
python character_converter.py p00-content <input-content-directory> <output-content-directory>
```

### Extracted p80 or p84

```powershell
python character_converter.py p8-content <input-content-directory> <output-content-directory>
```

### Repack as XC

```powershell
python character_converter.py pack-xc <converted-content-directory> <output.xc>
```

## 17. Recommended Normal Workflow

Use the following sequence for a new character.

```text
1. Extract the p00, p80, and p84 XC archives from the YW3 ROM.
2. Place one character's major files in the same input directory; strict mode requires all three.
3. Run strict --auto/character-xc, or explicitly select --copy-p00 for source-model preservation.
4. Confirm that all selected output XC archives exist; strict mode requires a complete trio.
5. Back up the original YWB1 XC archives.
6. Install and test p00, p80, and p84 incrementally.
7. If each succeeds, install the tested files as the final selected set.
```

The standard one-line command is:

```powershell
python character_converter.py ".\input\y473000\y473000_p00.xc" ".\converted\y473000" --auto
```

For intentional source p00 preservation, add `--copy-p00` and use a separate output directory for the experiment.

## 18. Historical Strict-Conversion Audit

The 2026-10-14 private development-corpus audit converted/repacked 2,843 of 2,949 supplied major XC files and left 106 unresolved: **104 p00 internal-conversion failures**, plus the two special motion failures in Section 13.11. Of the earlier 637 failures, 531 were recovered, including all 243 that had same-name B1 counterparts. These counts describe development evidence; the audited files and reports are not included in the public release.

This historical result describes strict conversion, not a copy-mode compatibility verdict. The 104 p00 files still lack supported internal downgrade handling; they are not thereby classified as impossible to transplant unchanged. `--copy-p00` explicitly preserves a container-valid source p00 without claiming that those internal formats were converted or that all those models were successfully tested in B1. The two motion forms remain conversion failures in every mode.

The 2026-10-15 copy-mode check exercised all 104 of those p00 cases in memory: every p00 output matched its original XC bytes, present motion outputs matched normal conversion, and missing slots were not generated. There were 103 p00-only sets and one complete trio (`y740000`). This check wrote no new XC files and did not establish game compatibility.
