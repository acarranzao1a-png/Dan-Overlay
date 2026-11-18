# msd527

MinaCalc v527 packaged as a stdin/stdout JSON filter, used **only to display**
the MSD that Etterna shows. The engine keeps calling `tools/bin/msd.exe`, which
is an older MinaCalc; changing the value the model consumes would invalidate the
rice model's calibration.

## Contract

```
stdin : [{"notes": 9, "time": 1.234}, ...]     time in seconds, already rate-scaled
stdout: {"overall": 27.2, "stream": ..., "version": 527}
```

`time` is divided by the music rate upstream, so the calculator is always called
at rate 1.0; applying the rate twice would shorten the chart twice.

## Usage

```
msd527.exe [goal] [ssr|msd]

  ssr   score-relative rating, the goal applies   (default: 1.0)
  msd   raw uncapped rating
```

## Build

Requires the Rust toolchain, a C++20 compiler and libclang (bindgen).

```
cargo build --release
copy target\release\msd527.exe ..\bin\msd527.exe
```

The build output is not tracked; only the source and the resulting binary are.

## Why the numbers differ from msd.exe

The two binaries are different MinaCalc versions. `jackspeed`, `technical` and
`handstream` come out identical to the millisecond, while `stream` and `stamina`
differ, which is the profile of the version that rewrote those two skillsets.
