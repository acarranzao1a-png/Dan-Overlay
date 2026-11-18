# qsr

Quaver Skill Rating for a 4K osu!mania chart, packaged as a small CLI, used
**only to display** a second difficulty number next to the MSD. Nothing in the
engine reads it.

It is a thin wrapper around [Quaver.API](https://github.com/Quaver/Quaver.API)
(MPL-2.0), which already ships an `.osu` parser and the key-mode difficulty
calculator, so no conversion step and no reimplementation are involved.

## Contract

```
qsr <file.osu>
stdout: {"qsr": 37.67, "keycount": 4, "valid": true, "notes": 1252}
```

| field | meaning |
|---|---|
| `qsr` | `DifficultyProcessor.OverallDifficulty` |
| `keycount` | columns reported by the converted map |
| `valid` | the conversion produced a usable map |
| `notes` | hit objects after conversion |

## `notes` is not decoration

The converter silently yields a truncated map on some inputs, and a rating
computed from three notes out of two thousand is worse than no rating at all.
The one case found so far is a chart carrying inherited timing points with
`-100` slider velocity, where the conversion stops after the first timestamp.

Callers must compare `notes` against the object count of the source file and
treat a large shortfall as "no rating available" rather than showing the number.

## Build

Requires the .NET 8 SDK. Quaver.API comes from NuGet, so no sources are vendored.

```
dotnet build -c Release
```

## What actually ships

Quaver.API declares MonoGame, ImageSharp, SQLite and friends, so a plain build
copies nineteen files. None of those are on the code path this program uses, and
removing them was verified against 42 charts across every tier: the calculator
only needs six files, 394 KB in total.

```
qsr.exe  qsr.dll  qsr.runtimeconfig.json  qsr.deps.json  Quaver.API.dll  DeepCloner.dll
```

`DeepCloner` is the only one that is genuinely loaded at runtime; without it the
process dies with a `FileNotFoundException` before parsing anything.

The output is framework-dependent, so it needs the .NET 8 desktop runtime on the
machine. If that is missing the process fails to start, which the caller must
treat as "no rating available" and fall back to MSD.

Build output is not tracked; the source and the six runtime files are.

