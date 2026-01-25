```bash
Content-addressed file store using BLAKE3

Usage: casq [OPTIONS] <COMMAND>

Commands:
  initialize       Initialize a new store
  put              Put files or directories to the store
  materialize      Materialize an object to the filesystem
  get              Output blob content and write it to stdout
  list             List tree children
  metadata         Show object metadata
  collect-garbage  Garbage collect unreferenced objects
  find-orphans     Find orphaned objects (unreferenced trees and blobs)
  references       Manage references
  help             Print this message or the help of the given subcommand(s)

Options:
  -r, --root <ROOT>  Store root directory (defaults to CASQ_ROOT env var or ./casq-store)
      --json         Output results as JSON
  -h, --help         Print help
  -V, --version      Print version

```
