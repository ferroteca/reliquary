# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""FreeDOS 1.4 plain-install recipe.

Installs FreeDOS 1.4 from the LiveCD distribution onto a hard-disk
image, taking the installer's "Plain DOS system" option. The current
implementation covers media acquisition and target disk creation; the
scripted installer run lands in a later milestone.
"""

import os

from relict import create_hdd_image

from ..home import install_media_dir, machine_dir
from ..media import ensure_media

MEDIA_URL = "https://download.freedos.org/1.4/FD14-LiveCD.zip"
MEDIA_SHA256 = ("2020ff6bb681967fd6eff8f51ad2e5cd5ab4421165948cef"
                "4246e4f7fcaf6339")
HDD_SIZE_MB = 20


def install():
    """Prepare the freedos-plain installation artifacts.

    Ensures the LiveCD media is cached and verified under the reliquary
    home and that the recipe's blank target disk exists. Returns a
    mapping with the ``media`` archive path and the ``hdd_image`` path.
    """
    media = ensure_media(
        MEDIA_URL, MEDIA_SHA256,
        os.path.join(install_media_dir("freedos"), "FD14-LiveCD.zip"))
    hdd_image = os.path.join(
        machine_dir("freedos-plain"), "drives", "hdd.qcow2")
    # An existing disk may hold an installed system; never clobber it.
    if not os.path.exists(hdd_image):
        create_hdd_image(hdd_image, HDD_SIZE_MB)
    return {"media": media, "hdd_image": hdd_image}
