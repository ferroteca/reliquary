# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""FreeDOS 1.4 plain-install recipe.

Installs FreeDOS 1.4 from the LiveCD distribution onto a hard-disk
image, taking the installer's "Plain DOS system" option. The current
implementation covers media acquisition and target disk creation; the
scripted installer run lands in a later milestone.
"""

import os
import socket
import sys
import time

from relict import MachineConfig, create_hdd_image, start, stop

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
    The call blocks while the machine runs (installer scripting is a
    later milestone; for now the guest runs until it exits or
    reliquary is interrupted) and the machine is shut down when
    install ends for any reason, including Ctrl-C. ``display`` shows
    the QEMU window instead of running headless.

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
        print("machine running; press Ctrl-C to shut it down",
              file=sys.stderr)
        _wait_for_exit(port)
    finally:
        _shutdown(port, machine_home)
    return {"iso": iso, "hdd_image": hdd_image}
