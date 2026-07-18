# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""relict - Windows 9x-under-QEMU automation harness.

Boot a Windows 9x guest headless in QEMU and run one program in it
from scripts: stage the executable on a virtual FAT drive, boot the
installed hard-disk image, execute the program with its output
redirected to a log on that drive, detect completion via
guest-initiated shutdown (Windows 9x offers no scrapeable text
screen), and hand back the log text uninterpreted - interpreting it
is the caller's job.

The staged drive is its own guest drive: C: is the boot image's
system drive and D: usually the virtual CD-ROM, so staged files
appear under a separate letter - E: by default, selectable with
``staged_drive=`` (D: is fine on a machine with no CD-ROM attached).

Unlike DOS, Windows 9x has no freely downloadable default guest:
the caller must supply the environment. The choice is either a ready
bootable hard-disk image (``boot_image=``, used as-is) or install
media - a Windows 9x CD ISO path (``install_media=``) or a download
URL (``media_url=``, which requires ``media_sha256=`` so the download
is verified) - plus any ``product_key=`` the unattended install
needs. From install media, ``install()`` builds the installed
hard-disk image exactly once per home. However relict arranges
execution inside the guest (e.g. a run hook baked into the image
during the unattended install) is its own business, invisible to
callers.

All on-disk state lives under the relict **home** directory, never
next to the installation. It defaults to a visible relict/ under the
user's Documents folder (falling back to ~/relict when no Documents
folder can be determined); override with the RELICT_HOME environment
variable, --home on the command line, or relict.set_home() from
Python. Layout under home: dist/ (boot.img, the installed bootable
hard-disk image, and any downloaded media artifacts) and staging/
(staged guest drive contents by convention, letter-named - e.g.
staging/e-drive for the default E:).

Embedders drive relict through the ``Runner`` surface: a
``Runner(RunnerConfig(...))`` instance is a configured Windows 9x
test machine - configuration only, never per-run state - exposing
``provision(dist_dir)`` and ``run(exe_path, args, home)`` with all
per-run state under the explicitly passed home.

STATUS: project scaffolding. The surface below records the agreed
design; the bodies are stubs raising NotImplementedError.

Commands (planned):
  install             ensure dist/boot.img exists, running the
                      one-time unattended install from the
                      configured media if it does not
  run "PROG.EXE"      run one guest program to completion and print
                      its redirected log
"""

import argparse
import dataclasses
import os


# ---- home directory ---------------------------------------------------------

#: The process-global home directory override set by set_home(), or
#: None for the default resolution described in home().
_home = None


def set_home(path):
    """Select the relict home directory for this process."""
    raise NotImplementedError("relict is scaffolding; not implemented yet")


def home():
    """The effective relict home directory: set_home()'s choice, the
    RELICT_HOME environment variable, a visible relict/ under the
    user's Documents folder, or ~/relict as the last resort."""
    raise NotImplementedError("relict is scaffolding; not implemented yet")


def dist_dir(home=None):
    """home/dist - the boot image and its installation artifacts."""
    raise NotImplementedError("relict is scaffolding; not implemented yet")


def boot_image(home=None):
    """home/dist/boot.img - the installed bootable Windows 9x
    hard-disk image."""
    raise NotImplementedError("relict is scaffolding; not implemented yet")


def staging_dir(*parts, home=None):
    """home/staging[/parts] - guest drive contents by convention."""
    raise NotImplementedError("relict is scaffolding; not implemented yet")


def drive_staging(letter="E", home=None):
    """home/staging/<letter>-drive - the conventional staging
    directory for the staged guest drive (staging/e-drive for the
    default E:)."""
    raise NotImplementedError("relict is scaffolding; not implemented yet")


# ---- guest environment ------------------------------------------------------

def _check_environment_choice(boot_image, install_media, media_url,
                              media_sha256, product_key):
    """Validate one guest-environment choice: a ready bootable image,
    or install media (a URL only together with the hash that verifies
    it), or nothing yet. Raises ValueError for an invalid
    combination."""
    media = (install_media, media_url, media_sha256, product_key)
    if boot_image is not None and any(v is not None for v in media):
        raise ValueError(
            "boot_image= is a ready environment; the install media "
            "options do not combine with it")
    if media_url is not None and media_sha256 is None:
        raise ValueError(
            "media_url= requires media_sha256=: the download is "
            "verified against it")


def _check_staged_drive(letter):
    """Validate and normalize a staged-drive letter: a single letter
    from D to Z - A: and B: belong to floppies and C: is the boot
    image's system drive. D: works only on a machine with no CD-ROM
    attached (the virtual CD-ROM usually claims it), hence the E:
    default. Returns the letter uppercased."""
    normalized = str(letter).upper()
    if len(normalized) != 1 or not "D" <= normalized <= "Z":
        raise ValueError(
            f"staged_drive={letter!r}: the staged guest drive needs "
            "a single drive letter from D to Z (A: and B: are the "
            "floppies, C: the system drive)")
    return normalized


def install(install_media=None, media_url=None, media_sha256=None,
            product_key=None, home=None):
    """Ensure boot_image() exists: a no-op when present, otherwise
    obtain the CD ISO (local path, or download verified against
    media_sha256) and run the one-time unattended install into a
    fresh hard-disk image. Raises ValueError when the image is absent
    and no media source is given - Windows 9x has no default
    environment."""
    _check_environment_choice(None, install_media, media_url,
                              media_sha256, product_key)
    raise NotImplementedError("relict is scaffolding; not implemented yet")


def run_guest_program(exe_path, args="", timeout=None,
                      staged_drive="E", home=None):
    """The full lifecycle for one Windows 9x executable: stage the
    (8.3-named) executable on the virtual FAT guest drive (appearing
    as `staged_drive`), boot boot_image(), run the program with its
    output redirected to a log on that drive, detect completion via
    guest-initiated shutdown, stop QEMU, and return the log text
    uninterpreted."""
    _check_staged_drive(staged_drive)
    raise NotImplementedError("relict is scaffolding; not implemented yet")


# ---- the runner surface -----------------------------------------------------

@dataclasses.dataclass(frozen=True)
class RunnerConfig:
    """What a Runner instance is constructed from. `boot_image` is
    the path of a ready bootable Windows 9x hard-disk image, used
    as-is; alternatively `install_media` (a CD ISO path) or
    `media_url` plus its mandatory `media_sha256` name the install
    media the one-time unattended install builds the image from,
    with `product_key` as that install requires - a ready image
    never combines with the install options, and neither choice has
    a default. `staged_drive` is the guest drive letter the staged
    virtual FAT drive appears as (default "E": C: is the system
    drive and D: usually the CD-ROM; D: works with no CD-ROM
    attached). `timeout` is the seconds allowed for one guest run;
    `qemu` is the QEMU binary path (default: found on the system);
    `qemu_args` are extra QEMU arguments."""

    boot_image: "str | None" = None
    install_media: "str | None" = None
    media_url: "str | None" = None
    media_sha256: "str | None" = None
    product_key: "str | None" = None
    staged_drive: "str" = "E"
    timeout: "float | None" = None
    qemu: "str | None" = None
    qemu_args: "tuple" = ()

    def __post_init__(self):
        _check_environment_choice(
            self.boot_image, self.install_media, self.media_url,
            self.media_sha256, self.product_key)
        object.__setattr__(self, "staged_drive",
                           _check_staged_drive(self.staged_drive))


class Runner:
    """A configured Windows 9x test machine: the generic runner
    surface for callers embedding relict (a soft contract; the
    module-level functions and the CLI remain the direct-use
    surface).

    An instance carries configuration only - never per-run state,
    which lives under the home directory passed explicitly to each
    operation - so one instance may serve concurrent runs in
    distinct homes."""

    platform = "win9x"

    def __init__(self, config=None):
        self.config = RunnerConfig() if config is None else config

    def provision(self, dist_dir):
        """Ensure the boot image exists at dist_dir/boot.img: keep a
        present image untouched, else copy the configured ready
        image, else run the one-time unattended install from the
        configured media. Raises ValueError when nothing is
        configured - there is no default Windows 9x environment.
        Deterministic given the config, and cache-unaware: durable
        caching of the installed image is the caller's job."""
        raise NotImplementedError(
            "relict is scaffolding; not implemented yet")

    def run(self, exe_path, args, home):
        """Run one guest program to completion inside `home` and
        return its output text uninterpreted. Boots
        home/dist/boot.img - provisioning it per the config when
        absent - and keeps all per-run state under `home`."""
        raise NotImplementedError(
            "relict is scaffolding; not implemented yet")


# ---- command line -----------------------------------------------------------

def main(argv=None):
    """The relict command line (planned surface; commands are
    stubs)."""
    parser = argparse.ArgumentParser(
        prog="relict",
        description="Windows 9x-under-QEMU automation harness "
                    "(scaffolding: commands are not implemented yet)")
    parser.add_argument("--home", help="relict home directory")
    sub = parser.add_subparsers(dest="command", required=True)

    p_install = sub.add_parser(
        "install",
        help="ensure dist/boot.img exists, running the one-time "
             "unattended install from the given media if it does not")
    p_install.add_argument("--install-media",
                           help="Windows 9x CD ISO path")
    p_install.add_argument("--media-url",
                           help="Windows 9x CD ISO download URL")
    p_install.add_argument("--media-sha256",
                           help="SHA-256 digest verifying --media-url")
    p_install.add_argument("--product-key",
                           help="product key for the unattended install")

    p_run = sub.add_parser(
        "run",
        help="run one guest program to completion and print its "
             "redirected log")
    p_run.add_argument("exe", help="Windows 9x executable (8.3-named)")
    p_run.add_argument("args", nargs="?", default="",
                       help="command-line arguments for the program")
    p_run.add_argument("--staged-drive", default="E", metavar="LETTER",
                       help="guest drive letter for the staged drive "
                            "(default: E)")
    p_run.add_argument("--timeout", type=float,
                       help="seconds allowed for the run")

    a = parser.parse_args(argv)
    return _dispatch(a)


def _dispatch(a):
    if a.home:
        set_home(a.home)
    if a.command == "install":
        install(install_media=a.install_media, media_url=a.media_url,
                media_sha256=a.media_sha256, product_key=a.product_key)
    elif a.command == "run":
        print(run_guest_program(a.exe, a.args, timeout=a.timeout,
                                staged_drive=a.staged_drive))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
