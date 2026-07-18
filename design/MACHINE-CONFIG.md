<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Machine configuration design

Status: direction established; no implementation is implied by this document.

## Purpose

relict should accept a declarative description of a QEMU machine. The same
configuration must be usable from `machine.json`, the Python runner interface,
and the direct Python functions.

The initial file format is JSON. JSON is in the Python standard library, has
one predictable data model, and maps directly to Python values. YAML is not
initially supported because a complete implementation would add a runtime
dependency, while a partial hand-written parser would not behave like real
YAML.

Machine configuration includes the existing runner settings and the new
hardware settings:

- platform, workflow timeout, DOS staging letter, and drive sources;
- QEMU executable, machine type, machine properties, and extra arguments; and
- declared drive sources and per-drive mount options.

It does not weaken platform selection, VM ownership, or the agentless DOS
fallback.

## Primary use cases

### Zero-configuration DOS default

With no `machine.json`, no machine configuration through Python, no
`--platform`, and no bootable drive under `<home>/drives`, relict retains its
complete zero-configuration behavior:

- the platform defaults to DOS;
- the verified FreeDOS boot image is downloaded and installed as
  `<home>/drives/floppy.img`;
- the existing DOS-compatible QEMU defaults are applied; and
- the agentless DOS workflow remains available.

Thus `relict start` against an empty home still produces a bootable FreeDOS
machine. Programmatic use has the equivalent baseline: `Runner()` carries
`MachineConfig()` defaults, resolves the established default home, and provisions the FreeDOS image there
when no bootable drive is declared. Present drives are never
overwritten.

### Local command-line use

The first primary user is a person operating relict directly from the command
line. The intended happy path is:

1. put one bootable image under `Documents/relict/drives` using its declared
   media name, such as `hdd.qcow2` or `floppy.img`;
2. specify the guest platform with `--platform` when it is not DOS; and
3. run the relevant relict command.

For example:

```powershell
Copy-Item .\windows-98.qcow2 `
    "$HOME\Documents\relict\drives\hdd.qcow2"
relict start --platform win9x
```

That should be enough for the ordinary case. The declared filename supplies
the medium, slot, and usual format. The selected platform workflow should
supply suitable defaults for QEMU machine type, memory, boot behavior, and
other hardware wherever one broadly compatible choice exists. relict must not
infer the platform from the image.

`machine.json` is optional for this user. A minimal file may specify only the
one setting that differs from the platform defaults:

```json
{
  "version": 1,
  "machine": "pc-i440fx-2.12"
}
```

Detailed or repeatable hardware configuration belongs in `machine.json`.
The CLI is intentionally not a flag-for-field mirror of the machine schema;
adding machine properties, per-drive options, and every QEMU setting as
individual CLI flags would produce a large shallow interface and two
configuration languages to maintain.

The CLI retains a small set of high-value operational controls. In particular,
`--platform` remains available and explicitly overrides a platform recorded in
`machine.json` for that invocation. Home selection, display choice, QMP port,
QEMU executable selection, and an explicit machine-file path are also
reasonable CLI controls because they select the execution context rather than
describe the emulated hardware in detail.

The existing raw QEMU-argument passthrough may remain as a diagnostic escape
hatch, but it is not the durable configuration interface. A command that needs
to be repeated or shared should put those arguments in `machine.json`.

### Programmatic use

The second primary user is a consuming test harness or other Python caller.
The Python interface exposes the complete machine configuration; the caller
does not need to create `machine.json` or translate its settings into CLI
arguments.

```python
config = relict.MachineConfig(
    platform="win9x",
    drives={"hdd_0": "images/windows-98.qcow2"},
)
machine = relict.Runner("run-home", config)
```

For any platform whose workflow is complete, a platform and one bootable
drive should be sufficient for the ordinary case. The platform workflow owns
compatible defaults for machine type, memory, controllers, boot behavior, and
interaction. The Python caller has access to the full configuration surface
when it needs to override those defaults, but is not required to restate them.

Until a platform workflow can honor that contract and is covered by hands-on
tests, it remains explicitly unimplemented rather than exposing a nominal
platform that requires callers to reconstruct undocumented QEMU details.

Programmatic use does not implicitly load `<home>/machine.json`. Automated
callers should not change behavior merely because an operator left a file in a
run home. `MachineConfig()` is a complete default machine, and explicit
constructor fields can express every setting supported by the file format.

A Python caller may deliberately use a machine file as its base:

```python
config = relict.MachineConfig.from_file(
    "machines/dos.json",
    timeout=90,
    qemu_args=("-cpu", "pentium",),
)
```

The file is normalized first and explicit Python values override it. This is
the only file-plus-Python layering model; `Runner` does not later discover and
merge another home file.

## `MachineConfig`

The configuration describes a machine, not behavior of the `Runner` object.
The public name is `MachineConfig`; it should be extended with the hardware
settings in this document.

`Runner` accepts an optional persistent home followed by the optional configuration. An omitted home resolves the
established process default once at construction:

```python
machine = relict.Runner("run-home", relict.MachineConfig(...))
```

There should not also be a public `MachineSpec`: two nearly synonymous values
would make callers learn an artificial distinction and would create merging
rules between them. One immutable `MachineConfig` is the normalization seam
for both file and Python input.

## One model, two representations

A JSON object and a Python mapping use the same field names and validation
rules. A caller may also construct and pass a `MachineConfig` directly.

The first file schema is:

```json
{
  "version": 1,
  "platform": "dos",
  "timeout": 120,
  "staged_drive": "D",
  "memory": 32,
  "qemu": "qemu-system-i386",
  "machine": {
    "type": "pc-i440fx-9.2",
    "accel": "tcg",
    "usb": false
  },
  "qemu_args": ["-cpu", "486"],
  "drives": {
    "hdd_0": {
      "source": "../images/dos.qcow2",
      "options": {
        "snapshot": true,
        "cache": "writeback"
      }
    },
    "hdd_1": {
      "options": {
        "discard": "unmap"
      }
    },
    "cdrom_0": {
      "source": "../images/tools.iso",
      "options": {
        "readonly": true
      }
    }
  }
}
```

`version` is required in a file and initially must be `1`. It is serialization
metadata rather than a constructor argument. Unknown fields and values of the
wrong type fail with an error that includes the configuration path, such as
`drives.hdd_0.options.cache`. Misspellings must not silently change the
machine.

The current `MachineConfig` fields retain their names and meanings:
`platform`, `staged_drive`, `timeout`, `memory`, `qemu`, `qemu_args`,
`machine`, and `drives`. JSON arrays normalize to immutable tuples where
appropriate.

`machine` supplies one QEMU `-machine` value. A string is shorthand for a
mapping containing only `type`; the mapping form requires a non-empty `type`
and may add string, number, or Boolean properties. Booleans normalize to
QEMU's `on` and `off`. An absent field preserves QEMU's default. A raw
`-machine` or `-M` in `qemu_args` conflicts with the structured field.

`memory` is a positive integer number of MiB and supplies one QEMU `-m`
value. It defaults by platform: 16 for DOS, 64 for Win9x, and 256 for WinNT.
A raw `-m` in `qemu_args` conflicts with the structured field.

`qemu_args` remains an array or tuple of complete command-line tokens, never
one shell command string. relict passes the tokens directly to `subprocess`
without shell splitting. Lifecycle-owned `-name` and `-qmp` options are
forbidden: relict must choose the identity and control endpoint required by
its ownership checks. `-drive` is also forbidden because attached media must
remain visible in the drive inventory described below.

## Drive inventory

The effective drive inventory is the union of:

- media declared by filename under `<home>/drives`; and
- drives with an explicit `source` in `MachineConfig.drives`.

The configuration uses logical slot names: `floppy_0` through `floppy_1`,
`hdd_0` through `hdd_3`, and ordered `cdrom_0` through `cdrom_3`. The existing
unindexed filesystem names still mean slot zero, so `drives/hdd.qcow2` and the
configuration key `hdd_0` refer to the same logical slot.

For the common case, a drive value may be a source path directly:

```json
{
  "version": 1,
  "platform": "win9x",
  "drives": {
    "hdd_0": "../images/windows-98.qcow2"
  }
}
```

This is shorthand for `{"source": "../images/windows-98.qcow2"}`. Python also
accepts a path-like value. A drive uses the object form only when it needs
mount options or future per-drive settings. Both forms normalize to the same
immutable drive entry before validation.

The resolved source path determines how it is attached. For a floppy or hard-
disk slot, a regular file is a QEMU disk image and a directory is a vvfat
staging drive. A CD-ROM source must be a regular image file; a directory is an
error because vvfat does not provide ISO9660 CD-ROM semantics. Callers do not
select vvfat with a separate option.

A slot may have only one source. If a configuration supplies
`drives.hdd_0.source` while `<home>/drives` contains `hdd.img`, `hdd_0.qcow2`,
or another slot-zero hard disk, resolution fails before QEMU starts. relict
never chooses one source by precedence.

Source resolution happens before provisioning, downloading, creating a
staging directory, or launching QEMU. The conflict rules are:

| Filesystem declaration | Configured entry | Result |
|---|---|---|
| `drives/hdd.qcow2` | no `hdd_0` entry | mount the filesystem image |
| `drives/hdd.qcow2` | `hdd_0` options only | mount it with those options |
| `drives/hdd.qcow2` | `hdd_0.source` set | error: two sources claim `hdd_0` |
| no slot-zero hard disk | `hdd_0.source` set | mount the configured source |
| no slot-zero hard disk | `hdd_0` options only | error: options have no source |

Two source declarations are an error even if their normalized paths happen to
be equal. A caller that wants to tune an image already declared under
`drives/` must omit `source` from the configured entry. This keeps the source
of every slot unambiguous and prevents precedence from changing after one path
is edited.

This supports reusable images without copying them into every relict home:

```python
config = relict.MachineConfig(drives={
    "hdd_0": {
        "source": r"D:\vm-images\dos.qcow2",
        "options": {"snapshot": True},
    },
})
```

An explicit source is mounted in place. relict does not copy, overwrite,
provision, truncate, or delete it. QEMU may write to an image source unless
its options make the mount read-only or transient. Callers should use
`snapshot: true` when several runs share a mutable base image, or
`readonly: true` when no writes are needed. An explicitly writable external
source is caller-owned persistent state; selecting it is an intentional
exception to relict-created state being contained under the home.

Relative source paths in `machine.json` are resolved from the directory
containing that file. Relative source paths passed through a Python mapping are
resolved from the current directory when the mapping is normalized. A
constructed `MachineConfig` stores normalized absolute paths, so later runs do
not reinterpret them relative to another working directory.

There are no special `boot_floppy_image` or `boot_hdd_image` shortcuts. A
source under the `drives` mapping is a declared machine drive and is mounted
directly, using the same inventory model as media declared under the home.
Boot selection is derived from that inventory unless an explicit boot-order
setting overrides it. When a DOS machine declares no bootable media, the
verified FreeDOS fallback remains an automatic platform behavior.

## Per-drive mount options

A configured drive entry may omit `source` and contain only `options`. It then
augments the filesystem declaration for that logical slot. If no source for
that slot exists, an options-only entry is an error rather than a declaration
of an empty drive.

The following QEMU `-drive` properties remain owned by relict and cannot be
set under `options`:

- `file`, because the resolved declaration supplies the source;
- `if`, `index`, and `media`, because the logical slot supplies them; and
- the vvfat source syntax for staged directories.

Other `-drive` properties may be supplied. Values use the same string, number,
and Boolean normalization as machine properties. `format` is allowed for
image files as an explicit override of the extension rule. Staged vvfat
directories remain `format=raw` and reject a configured format. A
configuration that makes the DOS workflow's selected staged drive read-only
also fails before QEMU starts.

CD-ROM keys retain their present meaning: their number orders them, while
relict places them on free IDE positions after hard disks. IDE capacity and
all existing slot-clash checks still fail closed.

## File discovery and explicit selection

CLI operations look for `<effective-home>/machine.json` when no explicit
machine file is selected. Its location under the effective home lets command-
line runs in different homes select different machines.

The CLI should add `--machine PATH` to commands that launch QEMU. An explicit
path selects that file instead of `<effective-home>/machine.json`; relative
paths are resolved from the caller's current directory. A missing explicitly
selected file is an error. A missing implicit home file means the existing
defaults.

CLI options do not reproduce the complete schema. They provide only common
operational controls and a few high-value selections. Detailed QEMU machine
properties and drive mount options are file-only at the CLI seam.

Only one file is loaded. There is no implicit search through parent
directories, includes, or multi-file merging, so the effective machine does
not depend on where a command happened to be launched.

## Python interface

`MachineConfig.drives`, `MachineConfig.machine`, and `MachineConfig.memory`
are implemented. Their constructors normalize and validate their values and
retain immutable configuration. A runner binds the normalized configuration
to one absolute home; all VM state remains under that home.

For example:

```python
machine = relict.Runner("run-home", relict.MachineConfig(
    platform="dos",
    memory=32,
    machine={"type": "pc", "accel": "tcg"},
    qemu_args=("-cpu", "486"),
    drives={
        "hdd_0": {
            "source": "images/dos.qcow2",
            "options": {"snapshot": True},
        },
    },
))
```

`MachineConfig.from_file(path)` and `MachineConfig.from_mapping(value,
base_dir=None)` provide explicit loaders and use the same validation as the
constructor. Both accept explicit field overrides. `from_file()` understands
`version`; it does not leak that serialization field into ordinary
construction.

Layering is deterministic:

- an explicitly supplied scalar replaces the file value, including an
  explicit `None` that clears an optional setting;
- `qemu_args` replaces the complete file array rather than concatenating it;
- `machine` replaces the complete file machine specification;
- `drives` merges by logical slot and then by entry field, with Python values
  winning; and
- per-drive `options` merges by option name, with Python values winning.

The implementation must distinguish an omitted constructor argument from an
explicit default-valued argument. For example, `platform="dos"` explicitly
overrides a file's `platform="win9x"`, even though DOS is also the ordinary
default. This specified-field bookkeeping is private implementation state and
does not enlarge the public interface.

The module-level launch and one-shot workflow functions accept one optional
`machine_config` value: a `MachineConfig`, mapping, or path-like object. Their
other parameters are operational controls such as display, port, and home;
machine settings are not duplicated as individual function parameters.

The QEMU executable is `MachineConfig.qemu`. It identifies the program used
to realize the machine, not the machine's emulated hardware type.

## Normalization seam

A machine-configuration module should own file loading, schema validation,
path resolution, immutability, conflict checks, and conversion of QEMU
hardware settings to launch arguments. Lifecycle code receives one validated
`MachineConfig` and does not know whether it came from JSON, a Python mapping,
or direct construction.

The media module remains responsible for discovering filesystem declarations,
assigning media and slots, and combining them with configured sources and
options. Platform workflows remain responsible for platform meaning, such as
requiring a writable DOS staging drive.

This forms one deep module: callers describe a machine once, while file
loading, validation, path rules, composition, and argument construction
remain local to its implementation.

## Resolution and precedence

Configuration resolution follows these rules:

1. For CLI use, an explicitly selected machine file supplies the base;
   otherwise `<effective-home>/machine.json` is loaded when present.
2. An explicitly supplied CLI `--platform` overrides the file's platform for
   that invocation. If neither supplies a platform, DOS remains the
   compatibility default.
3. Other basic CLI controls override their corresponding file values only
   where the CLI deliberately exposes that control.
4. For Python use, `MachineConfig(...)` supplies the complete configuration
   and performs no implicit home-file discovery.
5. `MachineConfig.from_file(path, **overrides)` or the equivalent mapping
   loader uses the selected file or mapping as a base and applies explicit
   Python values according to the layering rules above.
6. Lifecycle-owned identity and QMP arguments are always generated by relict
   and cannot be overridden.

After configuration and drive resolution, an effective DOS machine with no
bootable drive invokes the existing verified FreeDOS provisioning fallback.
This occurs only after drive-source conflicts have been ruled out and never
overwrites a present declaration.

Generated boot and memory defaults are added only when the effective
configuration does not already specify them. Per-drive options override the
inferred image format only where explicitly permitted; they never override a
source, medium, or slot.

## Diagnostics and safety

Configuration is fully validated before a QEMU process is created. Errors
identify the selected file when applicable and the failing configuration
path. Missing external sources, slot conflicts, forbidden properties, and
invalid option types therefore fail before launch.

The startup diagnostic retains the complete argument vector using safe
argument quoting, so invalid QEMU-specific values remain actionable. Machine
configuration cannot weaken ownership checks, port checks, child cleanup, or
platform selection. In particular, no configuration may select another QMP
endpoint or VM name, and machine type is never inferred from an image.

## Implementation sequence

With no explicit configuration, `MachineConfig()` supplies the complete
default machine. Files under `drives/` remain part of its drive inventory.

Implementation should proceed in independently verifiable steps:

1. **Implemented:** add JSON loading, validation, immutable normalization, and
   path-resolution tests.
2. **Implemented:** add configured-source and per-drive option composition tests, including
   external sources, same-path and different-path logical slot clashes,
   reserved keys, missing sources, staged directories, and read-only staging
   failures. Conflict tests must prove that no provisioning or process launch
   occurs after resolution fails.
3. **Implemented:** thread `MachineConfig` through lifecycle and workflow
   calls without changing the default argument vector.
4. **Implemented:** add the new fields and make `machine_config` the only
   machine-settings input to direct workflow functions.
5. Add CLI selection and implicit home discovery.
6. Document the file and Python forms in `README.md`, update `CHANGELOG.md` and
   `AGENTS.md`, and validate all command help.
7. Run lifecycle failure-path tests and the complete compile, unit-test,
   package-build, and `git diff --check` checks.

## Deferred extensions

- YAML may be added later through a justified parser dependency. If added, it
  must normalize through exactly the same model and must not introduce YAML-
  only features into the interface.
- Named profiles, includes, inheritance, environment interpolation, and
  multi-file merging are deferred. They would substantially enlarge the
  interface and are not needed to describe one machine.
- New media kinds, controllers, and USB devices should extend the declared
  media convention deliberately. They should not first appear as opaque raw
  `-drive` arguments.
