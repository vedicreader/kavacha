# Release notes

<!-- do not remove -->

## 0.0.4

- `graft` byte-compiles the grafted package as unchecked-hash `.pyc`, so importing it never writes into a signed bundle.
- `quit_cleanly` stops the process's multiprocessing children, then runs its atexit handlers with a time limit. The Dock delegate calls it from `applicationWillTerminate_`, because the C `exit()` behind Cmd+Q skips both.
- `quit_on_sigterm` turns SIGTERM into a Cocoa quit. `run_shell` installs it on macOS.

## 0.0.3

- `mend_frameworks` replaces a Frameworks library left with one library's header over another's body when two share a basename, and reports every shared basename. `finish` runs it.
- `sign` signs every Mach-O file once per inode, so hardlinks made by `link_duplicates` survive.
- `is_macho`, `macho` and `corrupt` read Mach-O headers without macholib.

## 0.0.2
kavacha relese to package webapps as mac or windows app
