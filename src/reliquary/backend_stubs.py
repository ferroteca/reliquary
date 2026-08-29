# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The two unbuilt adapters: VMware Workstation and Hyper-V.

Each is a real entry in the backend priority order (D66) and does a
real host probe — discovery actually works, since checking whether
the backend is installed costs nothing and gives an honest answer
either way. Everything past discovery is not built yet, and these
adapters say so.

They report no capabilities at all. That's what P11 requires here: a
capability nothing has tested is a capability nothing may claim, so a
stub claims none, and the assignment walk skips it even on a host
where the backend is actually installed. So the tail of the priority
order records an intent, not a working feature (D66) — the day one of
these adapters is actually built, what changes is this capability
report, not the priority walk itself.

If a blueprint pins ``backend`` to one of these, assignment fails at
preflight, naming both the backend and the fact that it isn't built
yet — rather than hitting the abstract method's bare
``NotImplementedError``. The request is a legal one that this build
just can't satisfy, which the error taxonomy classifies as a
PREFLIGHT ERROR (D58). The ``NotImplementedError`` inherited from
:class:`~reliquary.backends.BackendAdapter` still guards every
operation assignment can never actually reach.

VirtualBox used to be a stub in this module too, before it was built
out into its own module for F50 (``backend_virtualbox``).
"""

import os
import shutil
import sys

from .backends import Availability, BackendAdapter, Capabilities


def _which(binary, directories=()):
    """The first match for ``binary`` on PATH or in a common install location."""
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
    """Discovery only: reports available or not, and capable of nothing."""

    #: What the probe looks for on the host, used in the diagnostic
    #: message when it isn't found.
    looks_for = ""

    def capabilities(self):
        return Capabilities(backend=self.name)

    def _found(self, executable):
        home = (executable if os.path.isdir(executable)
                else os.path.dirname(executable))
        return Availability(
            self.name, True, executable=executable, home=home,
            detail=f"found at {executable}, but the {self.name} adapter "
                   "is unbuilt (it reports no capabilities, so "
                   "assignment passes over it)")

    def _absent(self):
        return Availability(
            self.name, False,
            detail=f"{self.looks_for} not found on this host")


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

    Hyper-V ships no console binary to look for, so the probe checks
    for its PowerShell module instead. That module only exists on
    Windows, which is what makes this adapter Windows-only — not a
    separate check, just a consequence of what it's looking for.
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
