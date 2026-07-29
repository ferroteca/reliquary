# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The three unbuilt adapters: VirtualBox, VMware Workstation, Hyper-V.

Each is a real entry in the backend priority order (D66) and a real
host probe — discovery works, because knowing whether VirtualBox is
installed costs nothing and is honest either way. Everything past
discovery is unbuilt, and says so.

**They report no capabilities**, which is the whole of P11 at this
seam: an untested capability is an unclaimed one, so a stub claims
nothing and the assignment walk passes over it even where the backend
is installed. The order's tail is therefore intent recorded, not
shipped behavior (D66) — and the day an adapter is built, what
changes is this report, not the walk.

A pinned ``backend`` naming one of these fails preflight naming the
backend and the gap, rather than raising the abstract-method
``NotImplementedError``: the request is legal and this build does not
satisfy it, which is a PREFLIGHT ERROR under the error taxonomy
(D58). The bare ``NotImplementedError`` inherited from
:class:`~reliquary.backends.BackendAdapter` guards the operations
assignment can never reach.
"""

import os
import shutil
import sys

from .backends import Availability, BackendAdapter, Capabilities


def _which(binary, directories=()):
    """The first of ``binary`` on PATH or in a conventional location."""
    found = shutil.which(binary)
    if found:
        return found
    for directory in directories:
        candidate = os.path.join(directory, binary)
        if os.path.isfile(candidate):
            return candidate
    return None


def _program_files():
    return [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]


class _StubAdapter(BackendAdapter):
    """Discovery only: available or not, and capable of nothing."""

    #: What the probe looks for, for the diagnostic's sake.
    looks_for = ""

    def capabilities(self):
        return Capabilities(backend=self.name)

    def _found(self, executable):
        return Availability(
            self.name, True, executable=executable,
            detail=f"found at {executable}, but the {self.name} adapter "
                   "is unbuilt (it reports no capabilities, so "
                   "assignment passes over it)")

    def _absent(self):
        return Availability(
            self.name, False,
            detail=f"{self.looks_for} not found on this host")


class VirtualBoxAdapter(_StubAdapter):
    """Oracle VirtualBox, driven through ``VBoxManage``."""

    name = "virtualbox"
    looks_for = "VBoxManage"

    def discover(self):
        binary = "VBoxManage.exe" if os.name == "nt" else "VBoxManage"
        directories = []
        if os.name == "nt":
            home = os.environ.get("VBOX_MSI_INSTALL_PATH") or ""
            directories = [path for path in [home] if path]
            directories += [os.path.join(root, "Oracle", "VirtualBox")
                            for root in _program_files()]
        else:
            directories = ["/usr/bin", "/usr/local/bin"]
        found = _which(binary, directories)
        return self._found(found) if found else self._absent()


class VMwareAdapter(_StubAdapter):
    """VMware Workstation, driven through ``vmrun``."""

    name = "vmware"
    looks_for = "vmrun"

    def discover(self):
        binary = "vmrun.exe" if os.name == "nt" else "vmrun"
        if os.name == "nt":
            directories = [os.path.join(root, "VMware",
                                        "VMware Workstation")
                           for root in _program_files()]
            directories += [os.path.join(root, "VMware", "VMware VIX")
                            for root in _program_files()]
        elif sys.platform == "darwin":
            directories = ["/Applications/VMware Fusion.app/Contents/"
                           "Public"]
        else:
            directories = ["/usr/bin", "/usr/local/bin"]
        found = _which(binary, directories)
        return self._found(found) if found else self._absent()


class HyperVAdapter(_StubAdapter):
    """Microsoft Hyper-V, driven through its PowerShell module.

    Hyper-V ships no console binary to look for: the probe is the
    module the host either has or has not, so it is Windows-only by
    construction rather than by policy.
    """

    name = "hyperv"
    looks_for = "the Hyper-V PowerShell module"

    def discover(self):
        if os.name != "nt":
            return Availability(
                self.name, False,
                detail="Hyper-V is a Windows hypervisor and this host "
                       "is not Windows")
        root = os.environ.get("SystemRoot", r"C:\Windows")
        module = os.path.join(root, "System32", "WindowsPowerShell",
                              "v1.0", "Modules", "Hyper-V")
        if os.path.isdir(module):
            return self._found(module)
        return self._absent()
