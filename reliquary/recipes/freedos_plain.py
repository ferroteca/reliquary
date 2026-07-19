# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""FreeDOS 1.4 plain-install recipe.

Installs FreeDOS 1.4 from the LiveCD distribution onto a hard-disk
image, taking the installer's "Plain DOS system" option. The current
implementation covers media acquisition, target disk creation, and
waiting for the LiveCD's first install menu, selecting "Install to
harddisk", accepting the default language and welcome screen,
confirming an unpartitioned drive C:, accepting the reboot prompt,
accepting the default keyboard layout, choosing the "Plain DOS
system" package set, and confirming the install; further installer
scripting lands in a later milestone.
"""

import os
import socket
import sys
import time

from relict import Machine, MachineConfig, create_hdd_image, start, stop

from ..home import install_media_dir, machine_dir
from ..media import ensure_media

MEDIA_URL = "https://download.freedos.org/1.4/FD14-LiveCD.zip"
ISO_MEMBER = "FD14LIVE.iso"
ISO_SHA256 = ("c48a9dcf4b8e22f44e268a9879745f0bd88c061195ac584e"
              "6ef2deb0477f81fb")
HDD_SIZE_MB = 20


def _vm_running(port):
    """Whether the machine still holds its QMP port."""
    try:
        socket.create_connection(("127.0.0.1", port), 1).close()
    except OSError:
        return False
    return True


def _wait_for_exit(port):
    """Block until the machine releases its QMP port."""
    while _vm_running(port):
        time.sleep(2)


def _shutdown(port, machine_home):
    """Stop the machine, tolerating one that has already exited."""
    try:
        stop(port, machine_home)
    except RuntimeError:
        pass  # already gone; relict cleaned up its recorded state


def install(display=False):
    """Run the freedos-plain installation machine.

    Ensures the LiveCD ISO is cached under the reliquary home and
    verified by SHA-256 on every run (the distribution zip is only a
    transient download and is deleted after extracting the ISO),
    ensures the recipe's target disk exists, and boots the machine
    through relict with the ISO and disk mounted, booting from the CD.
    After start, waits for the LiveCD's first install menu, selects
    "Install to harddisk", accepts the defaults for preferred
    language and the installer welcome screen, confirms partitioning
    drive C: and the required reboot, accepts the default keyboard
    layout, chooses the "Plain DOS system" package set (excluding the
    "with sources" sibling), and confirms with Yes on the ready-to-
    install prompt.
    The call then blocks while the machine runs (further installer
    scripting lands in a later milestone; for now the guest runs
    until it exits or reliquary is interrupted) and the machine is
    shut down when install ends for any reason, including Ctrl-C.
    ``display`` shows the QEMU window instead of running headless.

    Returns a mapping with the ``iso`` path and the ``hdd_image``
    path.
    """
    iso = ensure_media(
        MEDIA_URL, ISO_SHA256,
        os.path.join(install_media_dir("freedos"), ISO_MEMBER),
        archive_member=ISO_MEMBER)
    machine_home = machine_dir("freedos-plain")
    hdd_image = os.path.join(machine_home, "drives", "hdd.qcow2")
    # An existing disk may hold an installed system; never clobber it.
    if not os.path.exists(hdd_image):
        create_hdd_image(hdd_image, HDD_SIZE_MB)
    config = MachineConfig(drives={"cdrom_0": iso},
                           qemu_args=("-boot", "d"))
    port = start(config, display=display, home=machine_home)
    try:
        machine = Machine(port, machine_home)
        machine.wait_text(
            r"Welcome to FreeDOS 1\.4 \(LiveCD\)")
        machine.cursor_menu_select("Install to harddisk")
        machine.wait_text(r"What is your preferred language")
        machine.send_keys([["ret"]])
        machine.wait_text(
            r"Welcome to the FreeDOS 1\.4 installation program")
        machine.send_keys([["ret"]])
        machine.wait_text(
            r"Drive C: does not appear to be partitioned\.")
        machine.cursor_menu_select("Yes")
        machine.wait_text(r"You must reboot your computer")
        machine.cursor_menu_select("Yes")
        machine.wait_text(r"Please select your keyboard layout")
        machine.send_keys([["ret"]])
        machine.wait_text(
            r"What FreeDOS packages do you want to install\?")
        machine.cursor_menu_select(
            "Plain DOS system", exclude="with sources")
        machine.wait_text(
            r"We are now ready to install FreeDOS 1\.4\.")
        machine.cursor_menu_select("Yes")
        print("machine running; press Ctrl-C to shut it down",
              file=sys.stderr)
        _wait_for_exit(port)
    finally:
        _shutdown(port, machine_home)
    return {"iso": iso, "hdd_image": hdd_image}
