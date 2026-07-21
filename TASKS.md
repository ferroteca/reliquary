<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

Small to-do tasks.  Large tasks belong in the roadmap.

- allow specifying cache location outside of home dir
- tension between 'media/download' that we need to resolve
  - see 'inventory'
  - we haven't quite nailed the model concepts and their relationships yet:
    - a downloadable (cached) object:
      - can be an item needed at runtime
      - can be an archive containing multiple:
        - item needed at runtime
    - a locally (non-cache) specified object:
      - can be an archive?
      - can be in item needed at runtime
    - when 'cleaning'
      - ?? 
- 'list blueprints' should have a 'NAME' column and announce that these are scripts in <home_script_dir> (top line 
  instead of home dir announcement)
- new command 'diff blueprint <name>' should diff the user blueprint to the built-in blueprint of the same name
- new 'delete <blueprint>' command
  - warn if there are active child machines (wait for confirm or block)
    - if confirmed, stop machines
      - block if can't stop
  - delete machines 
  - delete blueprint
  - check if there are linked scripts
  - if they would be orphaned
    - if they exist (by name) in the built-in library
      - if there is a script difference between user & built-in
        - do not block, do not delete
        - clearly announce not delete script because it is different from the built-in version
      - else
        - delete script
- change "builtin library" concept to "template library" ??
- CLI do we need these (from cli help)\
  - --platform
  - --version (should be version with undocumented --version -v alias)
  - -h (should be help with -h --help undocumented alias)
- 'reliquary -h' should reflect command as "reliquary", 'rlq -h' otherwise
- --qemu --> --qemu-home
- locks lifecyle I see cache\machines\.locks\<blueprint>.lock"
  - when deleting machines/blueprints, should these be cleaned up?
  - i.e. what is the lifecycle, is this the right location?
- cli help
  - script "runs a scipt on a machine" not much more than that
- we need an 'inventory' report:
  - orphaned (listed first because, either you *really* want to keep it, or, you really *should* delete it)
    - media (specs not cached media)
    - scripts
  - blueprints
    - materialized
      - online machines
      - offline machines
    - unmaterialized
  - media
    - referenced
  - scripts
    - orphaned (should be listed first??)
    - referenced
- readme
  - blueprints and machines
    - give several clear examples to illustrate the concepts
      - e.g. 1mb ms-dos blueprint
        - QEMU machine #0
        - QEMU machine #1
        - QEMU machine #3 with a specific floppy image mounted
        - QEMU machine #4 with 16mb of memory and a specific cdrom mounted
- CLI 'clean', needs some serious thought
  - delete completely unreferenced media?
  - all downloads? unreferenced?
