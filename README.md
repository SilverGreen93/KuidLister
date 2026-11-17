# Kuid Lister

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/SilverGreen93/KuidLister)](https://github.com/SilverGreen93/KuidLister/releases/latest) [![Downloads (Latest Release)](https://img.shields.io/github/downloads/SilverGreen93/KuidLister/latest/total?label=latest%20release%20downloads)](https://github.com/SilverGreen93/KuidLister/releases/latest) ![GitHub all releases](https://img.shields.io/github/downloads/SilverGreen93/KuidLister/total?label=total%20downloads)

Utility for generating lists of Trainz KUIDs.

Paste a copy from Trainz Content Manager, and the app collects every kuid mention, drops the duplicates and hands back one comma separated list, ready to paste into a Download Center search or a `content-manage` command line.

## Getting Started

Download the latest Windows build from the Releases tab: the zip holds the GUI (`KuidLister.exe`) and the command line tool (`kuidlistercli.exe`), and the MSI installs both for the current user, with no administrator account needed.

## Building

The application is Python 3.9+ with a PyQt6 interface; `vbnet-original\` holds the Visual Studio / .NET Framework 4.8 sources it was ported from.

```
python -m pip install -e ".[gui]"            # the package plus its Qt binding
kuidlister-gui                               # run the GUI
Get-Content cm-copy.txt | kuidlister         # run the command line tool
pytest -q                                    # the unit tests
python build.py --only exe                   # Windows exes (also dmg, deb, zst)
```

The two entry scripts at the root of the repository do the same without installing the package: `python kuidlister_gui_entry.py` and `python kuidlister_cli_entry.py --upto 10`.

## Using the command line

KUIDs are read from stdin and the filtered list is written to stdout as one line, so it fits in a pipeline:

```
Get-Content cm-copy.txt | kuidlistercli > kuids.txt
type cm-copy.txt | kuidlistercli.exe --upto 10 > kuids.txt
```

`--upto <n>` does what the GUI's "Generate asset versions up to" checkbox does: every kuid is replaced by its versions from 0 to n (n between 0 and 127). The exit status is 0 when something was listed, 1 when the input held no kuid and 2 when the version limit was out of range.

## Issues and Feature requests

For any bugs, issues or feature requests, use the Issues tab in GitHub.

## Related Trainz tools

- [CDP Explorer](https://github.com/SilverGreen93/CDPExplorer)
- [TZarchiver](https://github.com/SilverGreen93/TZarchiver)
- [Kuid2Hash](https://github.com/SilverGreen93/Kuid2Hash)
