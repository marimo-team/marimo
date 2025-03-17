# Detailed Implementation Plan: Marimo's Persistence Subsystem Refactoring

## 1. Introduction and Goals

### 1.1. Overview

This document includes the detailed design and the implementation plan for refactoring of Marimo's persistence subsystem. **The goals of this refactoring are to enable (semi-)automatic cleanup and provide a more robust and flexible foundation different use cases: both *persistent cache* (already) and  *persistent cell execution* (in the future).**

This plan builds upon and synthesizes discussions from [#3176](https://github.com/marimo-team/marimo/issues/3176) and related issues.

The key improvements include:

*   **Content-Addressed Storage:**  Both entries and their contents will be stored using content-addressed filenames to ensure data integrity (and, secondarily, to enable deduplication), similarly to [Git's object database](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects), [git-annex](https://git-annex.branchable.com/internals/key_format/), and many backup systems.
*   **Separation between _entries_ and _contents_:** Multiple entries can reference the same contents (deduplication). In the initial implementation, both entries and contents are stored in the local file-system, in separate folders. This permits using different mechanisms for their synching/sharing and versioning, such as Git (for entries) and Dropbox (for contents).
    *   In the future, this separation will also enable **configuring different storage backends for entries and contents**, such as storing the entries in a server database such as PostgreSQL, and contents in object storage such as Amazon S3. This is inspired by [`jj`'s storage-independent backend APIs](https://jj-vcs.github.io/jj/latest/technical/architecture/#storage-independent-apis).
*   **Cleanup:**  A configurable cleanup mechanism will manage disk space usage, removing outdated or unnecessary persisted entries and contents.
*   **`Persister` Abstraction:**  A new `Persister` abstraction will encapsulate the storage logic, providing a clean interface for interacting with the persistent cache "facade" (Marimo's use-case; another possible future "facade" for the persistence subsystem would be persistent cell execution) and allowing for future extensions (e.g., SQLite entry storage, remote entry or content storage).
*   **`Entry` Data Structure:**  The existing `Cache` class will be replaced with a new `Entry` class, representing the contents of a `mo.persistent_cache()` block (or, in the future, a persisted cell) execution at a point in time. What comprises block's contents is discussed below.
*   **Legacy Support:**  Backward compatibility with the existing `PickleLoader` and `JsonLoader` will be maintained through a `LegacyPersister` implementation.
*   **Improved Concurrency:** The design incorporates lessons from [`jj`'s concurrency](https://jj-vcs.github.io/jj/latest/technical/concurrency/) to ensure that the persistence system is robust and safe for concurrent modifications even when there are non-cooperative Git checkout operations, Dropbox or other synchronization systems, the file system in which the content files are stored is network-attached and therefore unreliable, etc.

This plan prioritizes incremental implementation, starting with `FsPersister` that uses local file system for storing both entries and contents, stores entries in [TOML](https://toml.io/en/) files, and all content objects as separate files on the file system.

More advanced features, such as entry or content versioning, storing entries and content metadata in SQLite, "consolidating" lots of small content objects in a single file (a la Git's *object packs*), remote database-based `Persister`, and advanced content deduplication are deferred to future iterations.

### 1.2. Scope

This implementation plan focuses on the following core components of the persistence subsystem refactoring (currently used only for the **persistent cache** use-case):

*   **`Persister` Abstraction:** The core `Persister` abstract class is used instead of the legacy `Loader` when in *persistent caching* logic of the Marimo core. However, `MemoryLoader` is **not** replaced for *in-memory caching* (`mo.cache()`), although all loaders are changed to use `Entry` abstraction instead of `Cache`.
*   **`Entry` Abstraction:** The `Entry` class is defined and integrated into the Marimo core as a replacement of `Cache`.
*   **Filesystem-Based Storage via `FsPersister`:**  A concrete implementation of `Persister` that uses local filesystem-based storage for both entries and content. `FsPersister` is designed to be highly configurable in the future, but currently implements only a few concrete choices regarding entry and content storage.
*   **Entries stored in TOML:**  In the initial version of `FsPersister`, entries are stored as plain text, in TOML files.
*   **Cleanup Mechanisms:**  Cleanup mechanisms are implemented, allowing for the removal of entries (and, later, the contents referenced by these entries) based on a user-provided *cleanup strategy* function.
*   **Backward Compatibility via `LegacyPersister`:** `LegacyPersister` provides support for *existing* persistent cache "deployments" in `__marimo__/cache/` directories.
*   **API Changes:**  The necessary changes to the `App()` constructor permit graceful upgrade to the new persistence subsystem. If the `__marimo__/cache/` directory is present, the `App` will use `LegacyPersister` unless another implementation of `Persister` is explicitly passed to the `App()` constructor. If `__marimo__/cache/` is *not* present, `App` uses the new `FsPersister` that in turn creates and uses a different directory: `__marimo__/persist/`.
*   **`hash.py` Refactoring:** The `hash.py` code is decoupled from the storage abstraction (`Loader` or `Persister`). `mo.cache()` still uses `Hasher` and other functions from `hash.py` in conjunction with a `MemoryLoader`, while `mo.persistent_cache()` uses `hash.py` in conjunction with a `Persister` (`FsPersister` or `LegacyPersister`).

The following features are explicitly **out of scope** for this initial implementation plan and are deferred to future iterations:

*   *SQLite storage for entries and other metadata*
*   *SQLite storage for small contents*, to alleviate the burden on synchronization systems like Dropbox that can become bottlenecked by a large number of small files to sync that are also churned rapidly. A single SQLite file whose content is changed is less demanding of synchronization systems like Dropbox.
*   *Alternative `Persister` implementations* that use *remote databases* (like `PostgreSQL` or `Apache Cassandra`) and/or *object storage* (e.g., Amazon S3) for parts or all persistence, stage management, and synchronization that `FsPersister` currently does using local file system only, delegating cross-machine synchronization and/or backup to external mechanisms, ranging from Git to BorgBackup to Dropbox.
*   *Watched Files and integration of the persistence subsystem with them.* The [`mo.watched_file()` API](https://github.com/marimo-team/marimo/issues/3258) should make Marimo reactively respond to changes in the watched files.
*   *UI integration:* adding UI elements to manage persisted entries or select alternative, "non-deterministic" contents (cf. [#3270](https://github.com/marimo-team/marimo/discussions/3270))
*   *Block (cell) output and stderr persistence:* only block's *variables* are currently included in persisted entries' contents.
*   *Partial entry cleanup:* the initial cleanup mechanism deletes entire entries, though its trivial because currently entries have a single content kind: variables. The ability to selectively clean entries' contents, such as removing persisted blocks' *outputs* but keeping the *variables*, is a future consideration.
*   *Advanced content dedupication:* using Pickle's [out-of-band buffers](https://docs.python.org/3/library/pickle.html#out-of-band-buffers) and [persistend object references](https://docs.python.org/3/library/pickle.html#persistence-of-external-objects) to deduplicate persisted blocks' *variables* on a more fine-grained level, such as if multiple blocks or cells serialise different variables that thinly wrap the same or identical large dataframes.
*   *`FsPersister` working in [WASM notebooks](https://docs.marimo.io/guides/wasm/) (Pyodide runtime)* can be considered in the future. Cf. [Recommendations for including data in WASM notebook (#3194)](https://github.com/marimo-team/marimo/issues/3194).

### 1.3. Terminology

To ensure clarity and consistency throughout this document, the following terms are defined:

*   **`Persister`:** The top-level abstraction representing the persistence subsystem. It provides methods for storing, retrieving, and deleting persisted data.
*   **`ExecutionKey`:** An identifier for *a specific execution of a program block that is being persisted* (currently, a `mo.persistent_cache()` context block; in the future, it could also be a whole cell). The execution key includes the hash of the program block's code, the so-called *module hash* and the *execution time* called `created_at`. See the "Execution Key" section below for the details. An `ExecutionKey` object is used to store and retrieve the `Entry` via `Persister`'s `put()` and `get()` methods.
*   **`Entry`:** A class prepresenting the **entry**: the block's execution key plus the *contents* produced by the block execution. In the `Entry` object, the contents are Python objects: either not yet serialized on the "write path" in `Persister.put()`, or already deserialized on the "read path" in `Persister.get()`.
*   **`EntryMetadata`:** A "shallow" representation of the entry. It doesn't retrieve (and deserialise) the contents of the entry and doesn't even guarantee that the contents are still retrievable and deserializable. It only includes the information about *how* to retrieve the entry's contents from `Persister`. At some places in the document below, *entry* may refer to `EntryMetadata` rather than the "full" `Entry`.
*   **`ContentKind`:** A specific kind of persisted block's contents. Currently, the only recognized content kind is `variables`: the top-level variables defined in (and therefore "exported by") the `mo.persistent_cache()` context block (or, in the future, the whole cell). In the future, `output` and `stderr` content kinds are planned to be added. Currently, an entry can only have (at most) *one* content of a specific content kind. In the future, the introduction of "non-deterministic" contents may change this (cf. [#3270](https://github.com/marimo-team/marimo/discussions/3270)), but that's not certain yet.
*   **Content (Serialization) Format:** Specifies how the specific content is serialized. The content format is included in `EntryMetadata`, so that `Persister` knows how to deserialize the content. Currently, the only supported serialization formats are `pickle` or `json` (for the `variables` content kind). When `output` content kind is introduced, it might support multiple formats, too, apart from HTML (e.g., some of [Quarto's output formats](https://quarto.org/docs/output-formats/all-formats.html)).
*   **Variables:** The mapping of variable names to their values defined at the top-level of a `mo.persistent_cache()` context block (or, in the future, a whole cell) that are captured for persistence. This excludes function definitions, class definitions, and imports.
*   **Content Spec:** A mapping of `ContentKind`s to content formats, specifying which contents of an entry to retrieve and/or store and how. The content spec is passed to `Persister.get()` and `put()` methods. The content format can be specified as `auto`, indicating that `Persister`'s default should be used on the write path.
*   **(Entry) Content:** the content of an entry of a specific kind. The plural form, **entry contents**, usually refers to *all* contents persisted for some entry. *Content* may refer to either serialized representation (byte sequence) or "native" Python object, depending on the context. Due to deduplication, the content may "belong" to multiple entries.
*   **(Content) Object**: a byte sequence stored by `Persister`. Currently, the *whole* serialized representations (in `pickle` or `json` format) of the `variables` are stored as single objects. If finer-graned deduplication is implemented in the future, objects may also hold byte sequences that are only *parts* of some contents: e.g., large, byte-identical dataframes that are referenced from different `variables` of different entries. In the context of `FsPersister`, *object* may also be used as a synonym of *object file*, i.e., the file in which the object is stored.
*   **Object Hash:** The hash of the specific object. Used for (1) checking object *integrity* on the file system, (2) object *identification* (see the next item), and (3) object *deduplication*, all akin to [Git's objects](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects). Object hashes are always passed around and stored as [base64url](https://datatracker.ietf.org/doc/html/rfc4648#section-5)-encoded strings *without* trailing pad characters (`=`), rather than integer or `bytes` digests, to avoid confusion. See the "Object IDs" section below for the details on the hashing algorithm and encoding.
*   **Object ID:** The ID of the object that can be used to retrieve the object from `Persister`. By default, in the *deduplication mode*, object IDs coincide with the object hashes. If deduplication is disabled, in so-called *execution key-qualified mode*, object IDs also include parts of the execution keys of the entries these objects belong to. See the "Object IDs" section below for details.

We are making an attempt to separate general concepts and interfaces that are relevant to any `Persister` and those concepts and interfaces that may only be relevant to `FsPersister` or other Persisters partially derived from it. The concepts described below are currently only used by `FsPersister`:

*   **Entry Hash:** The hash of the entry metadata. See "Mapping Hashing" below for the details on the hashing algorithm. Since entry metadata includes the objects hashes (via object IDs) of the serialized contents of the entry, entry hash can also be seen as a hash of the "full" entry rather than just the entry metadata (the same technique is used to hash file trees in Git; [Merkle trees](https://en.wikipedia.org/wiki/Merkle_tree) are similar, too, although the entry hash is not cryptographically secure). The entry hash is used to check the entry metadata's integrity on the file system. Entry hashes are always passed around, stored, and used in downstream hashes (the snapshot hashes, see below) as 11-character base64url-encoded strings (without the trailing pad character `=`) rather than as 64-bit integer (8-byte) digests.
*   **(Entries) Snapshot:** The totality of entries recognised by `FsPersister` at some point, including some metadata about the snapshot itself, such as its *ancestor snapshots*. A snapshot is designed to be the *unit of synchronization of entries between machines running Marimo*, althrough the synchronization itself may be performed by other systems, such as Dropbox. Conceptually, snapshots are similar to *commits* in Git and other version control systems, and can be *included in* the commits in the same version control system in which the user tracks the Marimo notebook(s) that use the Marimo persistence system. In the future, snapshots could also be *implemented as* separate commits in a *branch* of the repo where the user stores Marimo notebooks, akin to [git-annex's branch](https://git-annex.branchable.com/how_it_works/).
*   **Snapshot Hash:** The hash of the whole snapshot *except* for the single key that stores this snapshot's hash itself. See the sections "Snapshot File Format (TOML)" and "Mapping Hashing" below for further details. Snapshot hashes serve as the names for the snapshot file themselves: `{snapshot_hash}.toml`, which means that snapshot files are content-addressed and deduplicated, too. This mirrors Git, where commits are stored as objects, and therefore commit objects are deduplicated. However, unlike Git, `FsPersister` stores snapshot files in a dedicated directory, separate from objects. Snapshot hashes are always passed around and stored (including in the snapshot file names) as 43-character base64url-encoded strings rather than 32-byte digests.
*   **_Fresh_ (Entries, Contents, Objects):** the entries (also the contents and the objects referenced from them) are called **fresh** if they haven't yet been included in any snapshot that have been seen by `FsPersister` on a specific machine (although, the snapshot might not have been *created* on the machine, it might have been created on a different machine and synched to this machine), and therefore haven't yet been synchronized to other machines and haven't yet become visible to `FsPersister`s operating on other machines. *Object cleanup* skips fresh objects to avoid a specific kind of conflict with external, non-cooperative synchronization systems such as Dropbox. The fresh markers of objects should themselves be stored and synchronized between machines. See the "Fresh Object Statuses" section for more details.

## 2. Python APIs and Behavior Spec of Any Persistence Implementation via `Persister`

### 2.1. ExecutionKey

```python
@dataclass
class ExecutionKey:
    block_id: str
    module_hash: str
    created_at: Optional[datetime]
```

The `ExecutionKey` uniquely identifies a specific execution of a program block (a `mo.persistent_cache()` context block or a persisted cell) that is being persisted. It includes:

1.   **`block_id`:** The id of the block that produced the entry. Currently, this is the hash of the code (AST) of the `mo.persistent_cache()` context block *without* considering either its variable or function deependencies. In the future, this may also be the hash of the cell code (for persisted cells), or the persisted cell's *name* (perhaps, qualified) if the cell is [named](https://docs.marimo.io/api/cell/#marimo.Cell.name).
2.   **`module_hash`:** The tree hash that includes the block's code (AST) hash and the hashes of the variable and function dependencies of the `mo.persistent_cache()` context block (or, in the future, the persisted cell). Variable and function dependency hashing algorithms are detailed below.
3.   **`created_at`:** A `datetime` (up to millisecond precision) indicating when the block executed started, which is considered the "entry creation time". This is an optional part of the execution key for entry retrieval: if not specified, `Persister` *must* retrieve the `Entry` whose `created_at` is the latest among the entries with `block_id` and `module_hash` matching those in the provided `ExecutionKey`.

`module_hash` includes (and therefore must uniquely identify) all the inputs to the execution, except for external, "real world" inputs, although the `created_at` captures the wall-clock time. Regardless, `block_id` is included in `module_hash`, and therefore don't add more identification information: if two execution keys have the same `module_hash`, they also have the same `block_id`. The primary purpose of including `block_id`s in the execution keys is grouping for enabling incremental and smooth (from user's perspective) *entry cleanup*. See a concrete example of using `block_id` for this purpose in the "Cleanup Strategy" section below.

**Alternatives considered:** Considered truncating `created_at` datetimes to a whole second. It didn't feel like it will be certainly enough for any conceivable use cases, so opted to the millisecond precision.

`block_id` (when it is a hash) and `module_hash` are SHA-256 hashes. The exact algorithms for computing these hashes are embodied by the `hash.py` code, and is not changed in the scope of the persistence subsystem refactoring, described in this document.

#### 2.1.1. Variable Dependency Hashing

TODO: specify the algorithm below more concretely.

Depending on the configuration, the specific variables, and what cells or non-marimo-cell Python code do they come from, the following could be used as the hashes of the variables:
*   `__hash__()` of the variable,
*    the hash of the byte sequence obtained by calling `memoryview()` on the variable,
*    the hash of the byte sequence obtained by calling `pickle.dumps()` or `json.dumps()` on the variable,
*    the `module_hash` of the `mo.persistent_cache()` context block (or a persisted cell) where the variable is defined.

#### 2.1.2. Function Dependency Hashing

Currently it's just the hash of the code (AST) of the function, without considering its own function dependencies.

### 2.2. Persister

```python
from typing import Any, Literal, Mapping, Optional

ContentKind = Literal["variables"]
ContentFormat = Literal["auto", "pickle", "json"]
ContentSpec = Mapping[ContentKind, ContentFormat]

class ExecutionKeyClash(Exception):
    ...

class Persister:
    @abstractmethod
    def get(
        self,
        execution_key: ExecutionKey,
        exact_match_created_at: bool = False,
        content_spec: Optional[ContentSpec] = None,
        **kwargs: Any,
    ) -> Optional[Entry]:
        """
        Retrieve an entry from the persistence subsystem.

        If `execution_key.created_at` is `None`, Persister returns the entry
        with the latest `created_at` and the same `block_id` and `module_hash` as
        in the provided `execution_key`.

        If `execution_key.created_at` is not `None`, `get()` returns the latest
        entry with `created_at` up to or equal to the `created_at` in the argument
        `execution_key` if `exact_match_created_at` is `False` (the default). If
        the caller is interested in an exact match of `created_at` only and doesn't
        need an `Entry` to be returned if there is no exact match,
        `exact_match_created_at=True` should be passed to `get()`.
        If `exact_match_created_at` is `True` and `execution_key.created_at` is `None`
        then `get()` raises a `ValueError`.
        
        kwargs are used to additionally parameterize the deserializer(s), e.g.,
        `Unpickler` or `JSONDecoder`. These arguments include the kwargs
        passed into the corresponding `mo.persistent_cache()` call in the
        notebook file.

        Returns `None` if the entry is not found or the entry metadata is corrupted.
        If the entry metadata is *not* corrupted but the deserialization of entry
        content(s) fails, the deserialization exception is re-raised from `get()`.
        """
        ...

    @abstractmethod
    def put(
        self,
        entry: Entry,
        content_spec: Optional[ContentSpec] = None,
        **kwargs: Any,
    ) -> Optional[EntryMetadata]:
        """
        Store the entry in the persistence subsystem.

        `entry.execution_key.created_at` must *not* be `None`.

        kwargs are used to additionally parameterize the serializer(s), e.g.,
        `Pickler` or `JSONEncoder`. These arguments include the kwargs
        passed into the corresponding `mo.persistent_cache()` call in the
        notebook file.

        Returns the entry metadata if the entry is successfully stored, or exactly
        the same entry has already been persisted before (this is extremely unlikely,
        given that `created_at` has millisecond precision, but possible).

        If this `put()` call has triggered a `cleanup()` and the entry has been
        cleaned up by the `CleanupStrategy`, `put()` *still* returns `EntryMetadata`
        even though a subsequent call to `get()` will not retrieve this entry.

        Returns `None` if `Persister`'s storage is unavailable (and `put()` may be
        re-tried later).
        
        If serialization of entry content(s) fails, the serialization exception is
        re-raised from `put()`.

        If an entry with the *same execution key* but *different contents* has already
        been stored, `put()` raises an `ExecutionKeyClash` exception.
        """
        ...

    @abstractmethod
    def cleanup(
        self,
        strategy: CleanupStrategy,
        include_content: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """
        Cleans up persisted entries based on the provided strategy.

        `include_content` indicates whether to cleanup just the entries or the
        contents (i.e., objects) referenced from those entries as well. The content
        cleanup could also be additionally parameterized via `kwargs`, e.g.,
        specifying the grace period before ophaned objects become eligible for
        cleanup. If `include_content` is not specified, it depends on this
        `Persister` subclass and the configuration of the specific instance whether
        it defaults to `True` or `False`.

        `kwargs` can also include additional arguments to the cleanup strategy:
        passed to `strategy.__call__()`.
        """
        ...
    
    @abstractmethod
    def on_exit(self) -> None:
        """
        Called by the Marimo runtime before it exists.

        `on_exit()` can call `cleanup()` with some default cleanup strategy
        and additional arguments, depending on the `Persister`'s subclass
        and its specific instantiation.
        """
        ...
```

### 2.3. Entry

The `Entry` dataclass replaces the existing `Cache` class.

```python
@dataclass(frozen=True)
class Entry:
    execution_key: ExecutionKey
    variables: Optional[Mapping[str, Any]]
    extra: Optional[Mapping[str, Any]]
```

The `extra` field is included for legacy compatibility. It stores any extra data that was present in the old `Cache` object's `meta` field, as well as the legacy `CacheType` (`Pure`, `ExecutionPath`, etc.). `LegacyPersister` needs to know `CacheType` to locate the content files in `__marimo__/cache`.

The `stateful_refs` field, present in the original `Cache` class, is *not* included in the `Entry`. This is because `stateful_refs` are specific to the runtime context and are not needed for persisted entries. For `mo.cache()`, `stateful_refs` are moved into `MemoryLoader`: `MemoryLoader` stores `stateful_refs` alongside the entries.

### 2.4. EntryMetadata

```python
class EntryMetadata:

    @property
    def execution_key(self) -> ExecutionKey:
        ...

    @property
    def created_at(self) -> datetime:
        v = self.execution_key.created_at
        if v is None:
            raise Exception("unexpected execution key without created_at")
        return v

    def content_size(self, kind: ContentKind) -> Optional[int]:
        """
        Return the total size in bytes of the serialized representation of
        the entry content of the given kind.
        """
        ...
    
    def content_format(self, kind: ContentKind) -> Optional[str]:
        """
        Return the serialization format (such as "pickle" or "json") of
        the entry content of the given kind.
        """
        ...

    def content_object_id(self, kind: ContentKind) -> Optional[str]:
        """
        Return the object id of the entry content of the given kind.
        
        Currently, this object is the serialized representation of the whole content.
        
        In the future, there might be additional objects that are needed to deserialize
        the content. The IDs for those extra objects might be obtained via a separate method,
        such as "extra_object_ids()", but this API is not decided yet. 
        """
        ...
    
    def has_content(self, content_kind: ContentKind) -> bool:
        """Returns whether the entry includes a content of the given kind."""
        ...
```

The `EntryMetadata` class encapsulates the details of how entry metadata is stored, allowing for future optimizations without changing the interface. For example, content sizes may be stored separately from the rest of the entry metadata and loaded lazily upon access through `EntryMetadata.size()` from the cleanup strategy.

### 2.4. Cleanup Strategy

The cleanup strategy function is passed to `Persister.cleanup()`. It receives a read-only collection of `EntryMetadata` objects, making it clear that the strategy should not modify that collection in-place.

The strategy function must return a collection of `ExecutionKey`s to be deleted. For now, entries are always deleted in full. Partial deletion of contents (e.g., deleting `variables` but keeping `output` content for entries) is not in the initial implementation plan.

```python
from collections.abc import Collection
from typing import Any, Protocol

class CleanupStrategy(Protocol):
    def __call__(
        self,
        entries: Collection[EntryMetadata],
        **kwargs: Any
    ) -> Collection[ExecutionKey]:
        """
        A strategy for cleaning up persisted entries. Must only be called by
        a `Persister`.

        `entries` is a collection of the metadata of all entries currently stored
        by the `Persister`. `Persister` guarantees that `execution_key.created_at`
        are *not* `None` for all `EntryMetadata` objects in `entries`. `Persister`
        also guarantees that all `entry_metadata.execution_key` objects are unique
        in this collection.

        kwargs includes any additional arguments passed down from
        `Persister.cleanup()` that may inform the strategy.
            
        The strategy must return a collection of execution keys whose corresponding
        entries should be **deleted** from the storage by `Persister`.
        """
        ...
```

Example usage:
```python
from collections import Counter
from collections.abc import Collection
from datetime import datetime, timedelta

def my_cleanup_strategy(
    entries: Collection[EntryMetadata],
    **kwargs: Any
) -> Collection[ExecutionKey]:
    """
    Delete entries with variables larger than 1MB and older than 30 days.

    Skip cleaning up entries that are sole entries for their blocks, if they
    are fresher than 7 days.
    """
    one_megabyte = 1024 * 1024
    thirty_days_ago = datetime.now() - timedelta(days=30)
    seven_days_ago = datetime.now() - timedelta(days=7)

    block_id_counts = Counter(e.execution_key.block_id for e in entries)

    keys_to_delete = []
    for e in entries:
        should_delete = (
            e.created_at < thirty_days_ago
            and e.has_content("variables")
            and e.content_size("variables") > one_megabyte
        )

        # Check if it's a sole entry for the block and is fresher than 7 days
        if should_delete:
            if (
                len(block_id_counts[e.execution_key.block_id]) == 1
                and e.created_at > seven_days_ago
            ):
                should_delete = False  # Skip deletion

        if should_delete:
            keys_to_delete.append(e.execution_key)

    return keys_to_delete
```

The default cleanup strategy for local file system-based persistence (`FsPersister`) is described in the section "Default Cleanup Strategy" below.

`LegacyPersister` doesn't implement `cleanup()`.

## 3. `FsPersister`: Local File System-Based Persistence

### 3.1. Persistence Directory Structure

```
my_project_dir/
├── .marimo.toml   # Has `[fs_persister]` table with the default FsPersister configs
├── __marimo__/
│   ├── persist/
│   │   ├── config.toml         # The essential configuration of this persistence directory
│   │   ├── locks/
│   │   │   ├── entry_log.lock
│   │   │   ├── modification.lock
│   │   │   └── objects.lock
│   │   ├── entry_snapshots/
│   │   │   ├── -_A1234567890123456789012345678901234567890.toml
│   │   │   ├── 1234567890123456789012345678901234567890A_-.toml
│   │   │   └── ...
│   │   ├── entry_log/
│   │   │   └── machine_46fe9d3c-4f08-4fcc-944f-4ab87e40b1f6.toml
│   │   ├── objects/
│   │   │   ├── 123456789-_abcdefghijklmnopqrstuvwxyzABCDEF
│   │   │   ├── 123456789-_abcdefghijklmnopqrstuvwxyzABCDEF.abcdefghijklmnopqrstuvwxyzABCDEF123456789_-.63875925237555
│   │   │   └── ...
│   │   └── fresh_objects/      # This dir may be absent, see "Fresh Object Statuses"
│   │       ├── 23456789-_abcdefghijklmnopqrstuvwxyzABCDEF
│   │       ├── 123456789-_abcdefghijklmnopqrstuvwxyzABCDEF.abcdefghijklmnopqrstuvwxyzABCDEF123456789_-.63875925237555
│   │       └── ...
│   └── temp/    # The proposed designated "tempdir" for Marimo, see "Atomic File Writes"
│       └── ...
├── ...
├── my_notebook.py
└── ...
```

#### 3.1.1. Persistence Directory Config

The persistence directory config: **`config.toml` file** currently has only one line:
```toml
version = "1"
```
`entry_storage_format = "toml"` is implied as the default, but not explicitly specified in `config.toml`. When and if SQLite-based entry storage is implemented, it might be indicated via `entry_storage_format = "sqlite"` in this `config.toml` file, but that's not certain yet. Alteranatively, `FsPersister` could look at the extensions of files (`.toml` or `.sqlite`) in `entry_snapshots/` and `entry_log/` directories (or, at the existence of the `entry_log/`: this "log" might not be needed for SQLite-based entry storage, SQLite's own WAL or rollback journal might fulfill the function of the log; see "Per-Machine Entry Log" below).

In general, `config.toml` is thought as a provision for potential incompatible changes to file and directory structure above that couldn't be inferred from the structure itself.

Note that the object ID mode shouldn't be configured in `config.toml`, and shouldn't even be uniform in one `__marimo__/persist/` directory. It's illustrated above, where an object ID in "deduplication mode" `objects/123456789-_abcdefghijklmnopqrstuvwxyzABCDEF`, coexists with an object ID in "execution key-qualified mode": `objects/123456789-_abcdefghijklmnopqrstuvwxyzABCDEF.abcdefghijklmnopqrstuvwxyzABCDEF123456789_-.63875925237555` (more details on these modes in the section "Object IDs" below). Rather, the object ID mode can be configured per `FsPersister`, in an `App()` constructor:
```python
from marimo import App, FsPersister

persister = FsPersister(object_id_mode="execution_key_qualified"))
app = App(persister)
```

This arrangement is reminiscent of SQLite, where individual *connections* to the same database can be configured drastically differently (via `PRAGMA` statements), even incompatibly with each other, but the database file (and its format) itself is still shared, and these very different connections may even work correctly as long as each accesses and writes to their own tables. In the case of local file system-based persistence subsystem:
*   The persistence directory structure outlined above (and, to some degree, the protocols for working with this structure: locking, snapshot creation, etc.) are like the SQLite database *file format*.
*   `FsPersister` *objects* are like *connections* to the SQLite database.
*   The default behaviour, where the `object_id_mode` is not explicitly passed to `FsPersister` (or, `FsPersister` is not explicitly passed to `App()`) can be controlled via [`.marimo.toml`](https://docs.marimo.io/guides/configuration/#user-configuration) (so-called *user configuration*). So, an option like `fs_persister.default_object_id_mode` can be added to to `.marimo.toml`. Extending the SQLite metaphour, this would analogous to SQLite's [compile-time options](https://www.sqlite.org/compile.html).

**Alternatives considered:** considered that directory-level `config.toml` shouldn't
be there at all, and instead all its options (currently, only `version`) are included in the `[fs_persister]` table in `.marimo.toml`. This would work if the `__marimo__/persist` dir would always remain *shared* for all notebooks that use the same `.marimo.toml`. However, there is a plan to support a separate persistence directory *per notebook*, discussed extensively in [#3176](https://github.com/marimo-team/marimo/issues/3176). In this situation, considering that different persistence directories may be created at different times when the `.marimo.toml` is different (and/or the Marimo app updated), it seems that directories may need to retain the flexibility of their own configs. For example, `fs_persister.default_entry_storage_format = "sqlite"` option in `.marimo.toml` may control what entry storage format the persistence directories for *new* notebook should be using, by including `entry_storage_format = "sqlite"` line in `__marimo__/persist/path/to/my_notebook.py/config.toml`. But the persistence directories created previously, without such a line, would still default to TOML entry storage format.

### 3.2. FsPersister Constructor and Default Configuration

`.marimo.toml` can include an `[fs_persister.defaults]` table with *default* `FsPersister` configurations, *unless* overridden in `FsPersister()` constructor call and then passed into `App()` constructor:
```toml
[fs_persister.defaults]
dir_path              = "persist"       # Relative to the __marimo__ dir location.
auto_variables_format = "pickle"        # Or: "json"
object_id_mode        = "deduplication" # Or: "execution_key_qualified"
entry_storage_format  = "toml"          # Currently, "toml" is the only supported value.

use_fresh_object_statuses             = true
cleanup_default_include_content       = false
cleanup_default_delete_orphan_objects = true

cleanup_on_exit             = true
entry_merge_timeout_seconds = 3600 # -1 means unlimited, also positive values are allowed
max_entries_in_log          = -1   # -1 means unlimited, also positive values are allowed
```

All the option values listed above are themselves default, so `[fs_persister]` table should be added to `.marimo.toml` (or [overridden via `pyproject.toml`](https://docs.marimo.io/guides/configuration/#overriding-settings-with-pyprojecttoml)) only if any configurations other than the above are desired.

All these options directly correspond to `FsPersister`'s constructor parameters:
```python
class FsPersister(Persister):
    def __init__(
        self,
        dir_path: Optional[str] = "persist",
        auto_variables_format: Literal["pickle", "json"] = "pickle",
        object_id_mode: Literal["deduplication", "execution_key_qualified"] = "deduplication",
        entry_storage_format: Literal["toml"] = "toml",
        use_fresh_object_statuses: bool = True,
        cleanup_default_include_content: bool = False,
        cleanup_default_delete_orphan_objects: bool = True,
        cleanup_on_exit: bool = True,
        entry_merge_timeout_seconds: int = 3600,
        max_entries_in_log: int = -1,
        default_cleanup_strategy: Optional[CleanupStrategy] = None
    ):
    ...
```

Regarding `use_fresh_object_statuses`, see the sections "Object Cleanup" and "Fresh Object Statuses" below for what this means and how it should be configured.

`cleanup_default_include_content` controls whether `FsPersister` cleans up the content (i.e., objects) in addition to entries during whenever `FsPersister.cleanup()` is called in background by `FsPersister` itself: see the full list of trigger conditions and entry points to this method in the "New Snapshot Creation" section below, *except* when the argument is explicitly overridden from the command line: `marimo persist cleanup --include_content[=true|false] [--] <notebook_paths>`.

`cleanup_default_delete_orphan_objects` controls whether `delete_orphan_objects` keyword argument is passed to `FsPersister.cleanup()` by default. See more details about this argument in the "Object Cleanup" section below. This argument can be overridden from the command line: `marimo persist cleanup --delete_orphan_objects[=true|false] [--] <notebook_paths>`.

`use_fresh_object_statuses=True` and `cleanup_default_include_content=False` are defensive defaults that assume the least permissive environment and prioritise synchronization correctness over ergonomics and simplicity. However, in a lot of cases `use_fresh_object_statuses=False` and `cleanup_default_include_content=True` configurations also work correctly and are more ergonomic. See the section "Object Cleanup" for details.

`cleanup_on_exit` controls whether `FsPersister.on_exit()` calls to `FsPersister.cleanup()` with the default cleanup strategy (see the next section), `include_content` and `delete_orphan_objects` equal to the `cleanup_default_include_content` and `cleanup_default_delete_orphan_objects` values passed into `FsPersister`'s constructor, respectively.

`entry_merge_timeout_seconds` and `max_entries_in_log` are configuration for entry log merge triggers: see the section "Per-Machine Entry Log" below.

#### 3.2.1. Default Cleanup Strategy

The `default_cleanup_strategy` argument to `FsPersister()` constructor controls the cleanup strategy that is used whenever `FsPersister.cleanup()` is called in background by `FsPersister` itself: see the full list of trigger conditions and entry points to this method in the "New Snapshot Creation" section below, except when the cleanup strategy is explicitly overridden in the `marimo persist cleanup` command (see below in this section).

In turn, if `default_cleanup_strategy` argument is not passed to `FsPersister()`, or if `FsPersister()` is not explicitly passed into the `App` constructor, the default cleanup strategy is created based on `[fs_persister.default_cleanup_strategy]` table in `.marimo.toml`:

```toml
[fs_persister.default_cleanup_strategy]
max_entries_per_block  = 3
max_entries_per_module = 2
max_entry_age_days     = -1
max_total_content_size = -1
```

These default cleanup strategy configurations behave as in the following code (the actual implementation might be different for example, using dataframes):
```python
from collections import defaultdict
from collection.abc import Collection
from datetime import datetime, timedelta

class DefaultCleanupStrategy:
    def __init__(
        self,
        max_entries_per_block: int = 3,
        max_entries_per_module: int = 2,
        max_entry_age_days: int = -1,
        max_total_content_size: int = -1,
    ):
        self.max_entries_per_block = self._validate(max_entries_per_block, "max_entries_per_block")
        self.max_entries_per_module = self._validate(max_entries_per_module, "max_entries_per_module")
        self.max_entry_age_days = self._validate(max_entry_age_days, "max_entry_age_days")
        self.max_total_content_size = self._validate(max_total_content_size, "max_total_content_size")
        if max_entries_per_block == -1 and max_entries_per_module == -1 and
            max_entry_age_days == -1 and max_total_content_size == -1:
            raise ValueError("At least one of the parameters should be positive")

    def _validate(self, value: int, param_name: str) -> int:
        if value <= 0 and value != -1:
            raise ValueError(f"{param_name} must be -1 or a non-negative integer")
        return value

    def __call__(
        self, entries: Collection[EntryMetadata], **kwargs
    ) -> Collection[ExecutionKey]:
        now = datetime.now()
        keys_to_delete: set[ExecutionKey] = set()

        if self.max_entries_per_block > 0:
            block_groups = defaultdict(list)
            for e in entries:
                block_groups[e.execution_key.block_id].append(e)

            for block_id, group in block_groups.items():
                group.sort(key=lambda e: e.created_at, reverse=True)
                for e in group[self.max_entries_per_block:]:
                    keys_to_delete.add(e.execution_key)

        if self.max_entries_per_module > 0:
            module_groups = defaultdict(list)
            for e in entries:
                module_groups[e.execution_key.module_hash].append(e)

            for module_hash, group in module_groups.items():
                group.sort(key=lambda e: e.created_at, reverse=True)
                for e in group[self.max_entries_per_module:]:
                    keys_to_delete.add(e.execution_key)

        if self.max_entry_age_days > 0:
            cutoff = now - timedelta(days=self.max_entry_age_days)
            for e in entries:
                if e.created_at < cutoff:
                    keys_to_delete.add(e.execution_key)

        if self.max_total_content_size > 0:
            remaining = [e for e in entries if e.execution_key not in keys_to_delete]
            total_size = sum(e.content_size("variables") or 0 for e in remaining)
            if total_size > self.max_total_content_size:
                remaining.sort(key=lambda e: e.created_at)

                # Create boolean array for latest entries per block
                is_latest = [False] * len(remaining)
                seen_blocks = set()
                for i in range(len(remaining) - 1, -1, -1):
                    block_id = remaining[i].execution_key.block_id
                    if block_id not in seen_blocks:
                        is_latest[i] = True
                        seen_blocks.add(block_id)

                current_total = total_size
                
                # First pass: remove non-latest entries per block
                for i, e in enumerate(remaining):
                    if current_total <= self.max_total_content_size:
                        break
                    if not is_latest[i]:
                        current_total -= e.content_size("variables") or 0
                        keys_to_delete.add(e.execution_key)
                
                # Second pass: remove latest entries if still over limit
                for i, e in enumerate(remaining):
                    if current_total <= self.max_total_content_size:
                        break
                    if is_latest[i]:
                        current_total -= e.content_size("variables") or 0
                        keys_to_delete.add(e.execution_key)

        return keys_to_delete
```

A one-time cleanup with the cleanup strategy configurations different from those defaults listed above or overridden in `[fs_persister.default_cleanup_strategy]` could be done from the command line:
```
marimo persist cleanup --max_entries_per_block=-1 --max_entries_per_module=-1 --max_entry_age_days=30 <notebook_paths>
```

### 3.3. External Synchronization

When the Marimo user(s) want to share across machines (or back up) the contents of persisted blocks stored via `FsPersister`, they currently should employ *external synchronization systems*.

For the rest of this document, we classify these systems as **cooperative** and **non-cooperative**.

**Cooperative (often *versioned*) synchronisation mechanisms** are those where synchronization is triggered from the command line and thus Marimo users can definitely know whether there are marimo cells executing concurrently when they are performing the synchronization. These include:
*   **Git itself**, perhaps even the same repository that is used for storing the Marimo notebooks (Python code). This can be a good option the total size of the content stored in the persistence directory is relatively small, and the content is primarily text (i.e., the `variables` in persisted entries contain primarily strings), and the entries are "churned" at a relatively low rate. Note that in the "Overview" section of this document, Git checkouts are called "non-cooperative"; that's because git checkout doesn't lock the files in the work tree during the checkout. `FsPersister` avoids conflicts due to non-cooperative work-tree checkout operations due to content-addressed naming of all files that are meant to be synchronized: entry snapshots and objects (except `config.toml`, but it's never changed after creation).
*   Git extensions for large and/or binary and/or frequently churning contents: [git-annex](http://git-annex.branchable.com/), [Datalad](https://www.datalad.org/) (itself a "wrapper" of git-annex), or [Git-LFS](https://github.com/git-lfs/git-lfs).
*   [DVC](https://dvc.org/) or other [data package managers](https://github.com/davidgasquez/handbook/blob/main/Open%20Data.md#data-package-managers).
 
**Non-cooperative synchronization and backup systems** are those that monitor the file system independently and can trigger synchronization as soon as they detect any changes. These include Dropbox, Box.com, OneDrive, Google Drive, iCloud, etc.

**Cooperative synchronization systems should be preferred** because they enable using a much simpler *object cleanup* procedure: see the "Object Cleanup" section below. However, `FsPersister` also has a mode 

**`locks/` and `entry_log/` directories should be excluded from synchronization**. However, it is harmless if the user forgets to exclude these directories from synchronization, or is "too lazy" to do so, although synchronization of `entry_log/` via non-cooperative systems ay cause significant but entirely unnecessary synchronization traffic.

The names of the entry log files: `machine_{machine_id}.toml` include the unique machine ID (using [`py-machineid`](https://github.com/keygen-sh/py-machineid)) to prevent conflicts between log files accidentally synced from other machines.

`__marimo__/temp/` should also be excluded from synchronization.

All other files and subdirectories in the persistence directory: `config.toml`, `entry_snapshots/`, `objects/`, and `fresh_objects/` *must* be synchronized.

The above guidance (regarding what files and subdirectories in the persistence directory should be included in and excluded from synchronization) applies regardless of the type of synchronization system that is being used: whether its the same Git repo that is used to manage and synchronize the notebook files themselves, a [data package manager](https://github.com/davidgasquez/handbook/blob/main/Open%20Data.md#data-package-managers) such as Datalad, DVC, etc., or a *non-cooperative* synchronization system, such as Dropbox, Box.com, OneDrive, Google Drive, iCloud, etc.

The persistence directory structure and protocols are specifically designed to be able to work concurrently with non-cooperative synchronization systems and/or non-cooperative file-system operations. Specific design decisions that are motivated by this consideration are described throughout the rest of this document.

### 3.4. Locks

The persistence directory has *file-based locks* (in the `locks/` subdir) to coordinate between concurrent `marimo` processes that could access, write to, or cleanup the persistence directory at the same time (intentionally or accidentally), *on the same machine*. These locks cannot protect from concurrent modifications made to the persistence directory on *different machines*, and hence the modifications that *are* intended to be synchronized, possibly non-cooperatively (see the previous section), namely *additions and removals of snapshots and objects*, are designed to be "lock-free", [adopting some techniques from `jj`](https://jj-vcs.github.io/jj/latest/technical/concurrency/).

`entry_log.lock` coordinates concurrent access and *truncations* of the entry log file (but not appends): see "Per-Machine Entry Log" below.

`objects.lock` coordinates *object cleanup* in `FsPersister.cleanup()` with new entry writing *with references to deduplicated objects* in `FsPersister.put()`.

`modification.lock` coordinates new entry writing in `FsPersister.put()` with *new snapshot creation* in `FsPersister.cleanup()`.

All locks are implemented an *empty, never-changing* SQLite database files. We piggy-back SQLite's cross-platform implementation of [shared-reserved-exclusive mode locking](https://www.sqlite.org/lockingv3.html) available to us through Python's standard [`sqlite3`](https://docs.python.org/3/library/sqlite3.html) module. The implementation is drafted [here](https://github.com/tox-dev/filelock/pull/399) (however, this code is going to be included in Marimo core source tree, without a dependency of `filelock` package).

All lock acquisitions are attempted with a timeout (or in a non-blocking regime, an acquisition attempt is made and if unsuccessful the method returns immediately) to prevent dead-locks.

If in the future `FsPersister` creates other SQLite databases, such as for storing small objects and *object metadata* (the object size, the object creation time, and the deletion time to enable object cleanup with a grace period, etc.), `objects.lock` might be replaced by the usage of the "actual" SQLite database file `objects.db`.

Currently, `entry_log.lock` and `objects.lock` are only acquired in the *shared* and *exclusive* modes, while `modification.lock` is only ever acquired in the *exclusive* mode.

**Alternatives considered:**
*   `modification.lock` to be an empty file, locked using `filelock` package. `entry_log.lock` and `objects.lock` locked using [APSW](https://github.com/rogerbinns/apsw) to access to SQLite's primitives directly rather than through `sqlite3` module, which requires maintaining "dummy" connections and opening dummy transactions to the database file to make SQLite to do file locking. Chose to use only the standard `sqlite3` module to minimise Marimo's dependencies and to simplify making `FsPersister` to work in WASM/Pyodide in the future.
*   A number of different locking arrangements were considered, including using only a single lock file or two lock files (instead of three), but with the usage of all three available locking modes (shared, reserved, and exclusive) on one of these lock files (whereas in the arrangement described above, two of the locks are only acquired in two out of three available locking modes, and the third lock is only acquired in the exclusive mode), and with the usage of *locking mode upgrades*. However, I couldn't find the arrangement with only two lock files (and with the SQLite's file locking mode transition affordances available through the `sqlite3` module) that would be *correct* from the concurrency perspective, for the current logic of "New Snapshot Creation" and "Entry Writing" procedures. The additional benefit of the locking arrangement described above is that it doesn't require SQLite's locking mode upgrades, which are more cumbersome to access through `sqlite3` (requires the usage of `PRAGMA locking_mode=EXCLUSIVE`) than non-upgradeable acquisitions in the shared and exclusive modes.

### 3.5. Entry Snapshots

`FsPersister` combines **immutable snapshot** files and **per-machine log** files to achieve correctness in most edge cases, including `marimo` process crashing (machine shutdown) in the middle of any `FsPersister` operation. (The remaining theoretically possible race conditions are described in the "Object Cleanup" section below.)

Snapshots are stored in `entry_snapshots/{snapshot_hash}.toml` files. When `FsPersister` creates a new snapshot, it includes *all* entries that is tracked by `FsPersister` at that moment. So, snapshots are fully "copy on write", and are **not** "delta-compressed" [like Git objects](https://git-scm.com/docs/git-pack-objects).
*   The decision to make snapshots fully self-contained might impact the scalability if the snapshots grow too large. The intended remedy for this is using a *separate persistence directory per notebook*, as discussed in [#3176](https://github.com/marimo-team/marimo/issues/3176), along with using sensible *cleanup strategies*.

Snapshots are **immutable**. Once created, they are never modified. This simplifies synchronization and avoids conflicts.

Snapshot file names are `{snapshot_hash}.toml`, which is computed from snapshot's entire content, excluding the `header.snapshot_hash` (see the "Snapshot File Format (TOML)" section below). This ensures snapshot integrity and enables deduplication of identical snapshots. See the "Mapping Hashing" section below on the hashing procedure. The `{snapshot_hash}` in the file name is a base64url-encoded representation of the snapshot hash. Example: `1234567890123456789012345678901234567890A_-.toml`.
*   **Alernatives considered:** considered including timestamps in snapshot file names, but the final design uses only snapshot hashes for simplicity and to avoid unnecessary merges of content-identical snapshot files.

A snapshot includes a DAG (directed acyclic graph) of its *ancestor snapshots* in the  `[parents]` table, up to a limited historical depth, such as recording at most 50 keys in the `[parents]` directory, while maximising the depth across "snapshot lineages". The `[parents]` DAG *is* included in the calculation of the snapshot hashes, so snapshots that contain the same *sets of entries*, but are produced from different histories have different snapshot hashes and hence are considered different snapshots. This is needed to prevent certain edge cases and race conditions involving synchronization. These DAGs are also used to quickly discard older snapshots that may be "resurrected" via synchronisation from other machines (see "New Snapshot Creation" below).
*   Note that unlike Git commits, the ancestor snapshots themselves are *not* kept around: in fact, `FsPersister` *deletes all ancestor snapshot* files after it writes the new one to the file system.
*   Another disanalogy of snapshots with Git commits is that the snapshot ancestry is of limited depth, and the older history is not maintained in any way, unless Git is used to manage and synchronize snapshot files themselves, which is a viable possibility, but is not required.

If the snapshot files are stored in Git, Git should *usually* recognise a new snapshot as a *rename* of the previously tracked snapshot file, thus displaying a small diff in Git interfaces like Github or Gitlab (as well as recording a smaller textual diff in the Git database itself, which could marginally help with scalability). This would be the case as long as the previous snapshot file is `git rm`-ed in the same commit as the new snapshot file added, which is the intended way to manage snapshots in Git if users choose to do so.

#### 3.5.1. Snapshot File Format (TOML)

Currently, `FsPersister` supports only textual TOML format for both entry snapshots and the entry log.

In snapshot file `1234567890123456789012345678901234567890A_-.toml` (except that the actual file wouldn't have any comments):
```toml
[header]
version = "1"
# Hash of the entire snapshot metadata, excluding the `snapshot_hash` key itself.
# This value must match the snapshot hash in the filename.
snapshot_hash = "1234567890123456789012345678901234567890A_-"
entry_table_name_parts = ["block_id", "module_hash", "created_at"]
[parents]
# Direct parents of this snapshot (because the key is equal to the value of `[header.snapshot_hash]` above).
# Elements in the list are sorted.
# Note that bare keys with trailing or leading `-` are acceptable in TOML. 
1234567890123456789012345678901234567890A_- = ["-_A1234567890123456789012345678901234567890", "_-A1234567890123456789012345678901234567890"]
# Record the snapshot ancestry up to a certain depth
-_A1234567890123456789012345678901234567890 = ["...", "..."]
_-A1234567890123456789012345678901234567890 = ["..."]
...

# The entry table, encoding the entry metadata. The "qualified name" of this table
# encodes the execution key of the entry, where the parts of the key map onto the execution key elements
# according to the `header.entry_table_name_parts` list above.
[abcdefghijklmnopqrstuvwxyzABCDEF123456789-_.abcdefghijklmnopqrstuvwxyzABCDEFGH123456789.63875925237555]
variables = { id = "123456789-_abcdefghijklmnopqrstuvwxyzABCDEF", size = 123, format = "pickle" }
hash = "mIG4wyNQHrw" # Entry hash: the value is a base64url-encoded string.

# Another entry table
[abcdefghijklmnopqrstuvwxyzABCDEF123456789-_.abcdefghijklmnopqrstuvwxyzABCDEF123456789_-.63875925237556]
...
```

`version="1"` is the version of this snapshot file format rather than the persistence directory structure. So, it may *not* match the `version` in `config.toml`.

`block_id` (when it is a hash) and `module_hash` parts of the execution keys in TOML table names are represented as 43-character [bare keys](https://toml.io/en/v1.0.0#keys), obtained via `base64.urlsafe_b64encode(hash_digest)[:-1]`, stripping the `=` pad character at the end.

`created_at` parts of the execution keys (of `datetime.datetime` type) in TOML table names are represented as bare, digit-only keys, computed as:
```python
from datetime import datetime, timedelta
def created_at_millis(created_at: datetime) -> int:
    td = created_at - datetime.min
    return str(int(td / timedelta(milliseconds=1)))
```

With `created_at` datetimes around the current moment, these keys have 15 digits, the first of digit is 6.

`header.entry_table_name_parts` is the provision for forward-compatibility with potential addition of `version` element to the the execution key, as discussed in [#3176](https://github.com/marimo-team/marimo/issues/3176). The upgrade may look like this:
1. A new version of `marimo` that supports `version` in execution keys loads the previously created snapshot, but since it doesn't see `"version"` in the `header.entry_table_name_parts`, it assumes the version is equal to `0` in all execution keys for all entries stored in this snapshot.
2. When this `marimo` process creates a new snapshot, it adds `"version"` to `header.entry_table_name_parts` and also adds `.0` in all the entry table names.

The algorithm of computing the entry hashes is described in the "Mapping Hashing" section below.

**Alternatives considered:**
*   Considered using `created_at.isoformat(timespec='milliseconds')` as `created_at` representation for entry storage, such as `"2024-03-20T14:30:15.123"` (quoted TOML keys). That would be more human-readable. However, chose `created_at_millis` representation for consistency with execution key-qualified mode for object IDs (see the section "Object IDs" below) and consistency with possible alternative `Persister` implementations (either also file system-based, or using remote object storage), where the `created_at` can be a part of a path and ISO format with `:` characters may not be admissible.
*   Considered adding `header.default_variables_format` key that permits shrinking the snapshot files because usually `variables = { ..., format = "pickle" }` will be repeated throughout the file. This optimisation could be implemented in the future, but is left out of scope of the design described in this document.
*   Considered using content formats like `pickle_5`, where the `5` is the [Pickle protocol version](https://docs.python.org/3/library/pickle.html#data-stream-format). However, this seems unnecessary because Pickle already includes the protocol version byte in the serialized byte sequence, so it should transparently handle potential protocol version mismatches for us. But just in case, the protocol version could be passed down via `mo.persistent_cache(..., protocol=N)` that will pass down `kwargs` to `FsPersister`'s `get()` and `.put()` calls, who in turn pass these `kwargs` down to `Unpickler()` and `Pickler()`.

### 3.6. Per-Machine Entry Log

`FsPersister.put()` appends new entries to the `entry_log/machine_{machine_id}.toml` file. Usually, `FsPersister` merges these entries with the snapshot(s) and creates a new snapshot *less frequently than upon each `FsPersister.put()` call*, only on certain trigger conditions:
*   **`FsPersister` detects a new snapshot in `entry_snapshots/`** and starts to merge snapshots anyways.
*   **Marimo process exits**, calling to `FsPersister.on_exit()` before that. This trigger is controlled by the `cleanup_on_exit` configuration parameter, see the section "FsPersister Constructor and Default Configuration" above. Default value is `True`.
*   **Entry merge timeout:** Some entries have been hanging in the log file and haven't been merged into a snapshot for longer than a configured duration. This trigger is controlled by the `entry_merge_timeout_seconds` configuration parameter. The default value is 3600 seconds (1 hour).
*   **Log size:** the log has more entries than a configured limit. This trigger is controlled by the `max_entries_in_log` configuration parameter, the default value is -1, meaning that the log size is not limited.

The first trigger is always on. Triggers 2-4 are all optional, but at least one of them should be enabled because otherwise the log file may never be merged into a snapshot (unless `Persister.cleanup()` is called explicitly, via a dedicated CLI command a la `marimo persist cleanup`).

Unlike log-structured DBs like RocksDB, the log merge is not an optimisation: parsing the log TOML file is exactly as fast as parsing the snapshot TOML file. However, `FsPersister` uses the log merge (as a part of the more general "New Snapshot Creation" process, described below) as an opportunity to call the *cleanup strategy*, so some entries that have been added to the log may not even appear in the new snapshot.

**The entry log file is *not* intended to be synchronized across machines.** Users should exclude the `entry_log/` directory from synchronization services like Dropbox. If Git is used to store and sync persistence metadata, add `entry_log/` to `.gitignore`. Normally, the `entry_log/` directory should have a single file on any specific machine, unless the user neglected excluding the `entry_log/` directory from synchronisation (via Dropbox's "selective sync" feature, `.gitignore`, etc.). `FsPersister` *doesn't* monitor the `entry_log/` directory for any other files than its "own" `machine_{machine_id}.toml`.

The log file name is `machine_{machine_id}.toml`, where `machine_id` is the unique GUID of the machine, obtained via `machineid.id()` from [`pymachineid`](https://github.com/keygen-sh/py-machineid) package. `pymachineid` doesn't have any native code and is [just about 100 LOC](https://github.com/keygen-sh/py-machineid/blob/master/machineid/__init__.py), so it should probably be embedded into Marimo core source tree rather than added as a dependency.

Two types of modification are done on the log file:
*   **Append a new entry** during a "normal" `FsPersister.put()`, i.e., one that doesn't trigger the creation of a new snapshot.
*   **Truncate entries** during the new snapshot creation (see the detailed description below).

Both types of modifications require holding the `modification.lock` in the *exclusive* mode because [CPython doens't support O_APPEND atomicity guarantees on Windows](https://github.com/python/cpython/issues/86772).

In addition, a separate `entry_log.lock` is used to mutually exclude log file *reads* (e.g., during the re-loading: see "Log Monitoring and Re-Loading" below) with truncations (but not with appends: they can happen concurrently with log file reads).

Holding `modification.lock` in the exclusive mode on log appends could only possibly become a point of contention if two or more `marimo` processes write to the log concurrently and at very frequencies. The intended remedy for this is using a *separate persistence directory per notebook* (a planned feature), as discussed in [#3176](https://github.com/marimo-team/marimo/issues/3176).

Unlike snapshot writing and object writing, `FsPersister` does *not* attempt to make log appends atomic on the file system (this can quickly become too wasteful as the log grows, due to quadratic write amplification). This *may* lead to corrupted entries, and even the log file to be a malformed TOML, if the machine loses power at a very unfortunate moment. This necessitates *entry integrity checking* (see "Entry Conflict Resolution and Integrity Checking" below) and a "hardened" TOML parsing approach (the log file is parsed top to bottom during the "New Snapshot Creation" procedure): instead of simply using the stock TOML parsing library like [`tomli`](https://github.com/hukkin/tomli), `FsPersister` first splits the file into tables on a "definitely well-formed" table headers matching the `\[[^\[\]]+\]` regexp (this is valid for the subset of TOML grammar actually used in the entry log file) and then parsing the text ranges between the matched table headers individually.

**Alternatives considered:**
*   A single log file such as `log.toml` (rather than a *per-machine* log file with name `machine_{machine_id}.toml`, as described above) that would be synchronized across machines
*   Chunked log files with timestamps in their names,
*   Appending entries directly to "unified" TOML file with entries: that is, not differentiating snapshots and logs.

Ultimately, the per-machine log approach simplifies concurrency and should avoid interference with non-cooperative synchronization services like Dropbox.

#### 3.6.1. Log Monitoring and Re-Loading

`FsPersister` monitors the entry log file using `marimo._utils.FileWatcher` if the `mtime` or the file size don't match those previously observed by this `FsPersister` during the initial load or during subsequent log appends in `FsPersister.put()`, re-loads the entries from the log in background. This is needed to keep entry sets up-to-date between concurrent `marimo` processes.

`FsPersister` determines that it needs to re-load the log *from the beginning* rather than from the last loaded offset (by this `FsPersister`, i.e., by this `marimo` process) by checking if the range of bytes just before the last loaded offset matches the entry table that this `FsPersister` loaded. `FsPersister` holds the `entry_log.lock` in the *shared* mode from the beginning of the "last loaded entry check" and until it reads the reminder of the log file (or the whole file, if the check has failed) into its memory, and releases the lock before it starts to parse the entries and check their integrity (see "Entry Conflict Resolution and Integrity Checking").

If `FsPersister` sees that the entry log should be re-loaded from the beginning, it means a concurrent `marimo` process has created a new snapshot that should appear in the `entry_snapshots/` directory. However, the background thread that monitors and re-loads the log file doesn't need to do anything about this: another thread will trigger the loading of the new snapshot via the "New Snapshot Creation" procedure (see below).

#### 3.6.2. Log File Format (TOML)

Unlike snapshots, log files don't have a `[parents]` table and don't include a file hash analogous to the snapshot hash because logs are machine-local, temporary, and appendable.

Otherwise, the log file format is the same as the snapshot file format.

Example, in file `machine_46fe9d3c-4f08-4fcc-944f-4ab87e40b1f6.toml` (except that the actual file wouldn't have any comments):
```toml
[header]
version = "1"
entry_table_name_parts = ["block_id", "module_hash", "created_at"]

# Entry table
[abcdefghijklmnopqrstuvwxyzABCDEF123456789-_.abcdefghijklmnopqrstuvwxyzABCDEFGH123456789.63875925237555]
variables = { id = "123456789-_abcdefghijklmnopqrstuvwxyzABCDEF", size = 123, format = "pickle" }
hash = "mIG4wyNQHrw" # Entry hash

# Another entry table
[abcdefghijklmnopqrstuvwxyzABCDEF123456789-_.abcdefghijklmnopqrstuvwxyzABCDEF123456789_-.63875925237000]
...
```

Note that due to inter-process races, the `created_at` of subsequent entry tables' execution keys are not guaranteed to be ascending: for example, above, the entry table with the creation time `63875925237555` comes before the one with `63875925237000`, which is "earlier". `FsPersister` doesn't rely on such an ordering.

#### 3.7. New Snapshot Creation

The "target" state of `entry_snapshots/` is to have a single file. `FsPersister` monitors the `entry_snapshots/` directory using the `watchdog` library (or a fall-back a la `marimo._utils.FileWatcher`) for the appearance of new files (presumably synced from other machines) and proactively merges them along with whatever entries are present in the log file at the moment into a new, unifying snapshot.

`FsPersister.cleanup()` *is* the new snapshot creation procedure. Entry cleanup without creation of a new snapshot is not permitted. To create a new snapshot without cleaning up any entries, `FsPersister.cleanup()` should be called with the dummy cleanup strategy: `lambda _: []`.

In addition to the standard arguments for `Persister.cleanup()` (`strategy` and `include_content`), `FsPersister.cleanup()` detects extra keyword arguments:
*   `delete_orphan_objects: Optional[bool]`, defaulting to the value passed as `cleanup_default_delete_orphan_objects` to the `FsPersister()` constructor, which in turn defaults to the value for the `fs_persister.defaults.cleanup_default_delete_orphan_objects` in `.marimo.toml` (see the section "FsPersister Constructor and Default Configuration" above), which in turn defaults to `true`.
*   `log_entries: list[EntryMetadata]`, which should be passed when `cleanup()` is called from `FsPersister.put()`: see the "Entry Writing" section.

**New Snapshot Creation Algorithm:**
In `FsPersister.cleanup()`:
1.   If `cleanup()` is called with `delete_orphan_objects=True` or `log_entries` not equal to `None`, skip to the step 4.
2.   List all files in `entry_snapshots/` and re-load the entry log file (see "Log Monitoring and Re-Loading").
3.   If all files in `entry_snapshots/` have names of the form `{snapshot_hash}.toml` and their snapshot hashes are listed as ancestors (direct or indirect parents) of the last snapshot loaded or created by this Marimo process, the last loaded or created snapshot is listed (i.e., it is *not* deleted from `entry_snapshots/`), *and* the log file is empty (or, more precisely: the log file has only the `[header]` table and at most one other table, and that other table doesn't appear to be an entry table that passes the integrity check), exit from `cleanup()`.
4.   If `cleanup()` is called with `include_content=True` **or** `delete_orphan_objects=True`, acquire `objects.lock` in the *exclusive* mode. This is needed to prevent possible races with concurrent `FsPersister.put()` calls (see the "Entry Writing" section below) on the same persistence directory, from the same Marimo process (if this `cleanup()` call is done from a background thread) or from a different Marimo process.
5.   Acquire `modification.lock` in the *exclusive* mode, to ensure that only one Marimo process does the actual new entry creation in this persistence directory at any time. If `FsPersister.cleanup()` is called from `FsPersister.put()`, `modification.lock` is already held, so this step will be a re-entrancy counter increment.
6.   List the `entry_snapshots/` directory again and read all files in it.
7.   Recover the correct snapshot file names (from their `header.snapshot_hash` keys rather than file names, see "Snapshot File Format (TOML)"), ignore all files in `entry_snapshots/` that are not well-formed TOML files or appear to be corrupted snapshots (their `header.snapshot_hash` doesn't conform with the rest of the file).
8.   Move all non-corrupted snapshots to their "proper" names like `{snapshot_hash}.toml` unless other non-corrupted snapshots already exist at these names.
9.   Re-load the log file again unless `cleanup()` is called with `log_entries` keyword argument from `FsPersister.put()`: see the "Entry Writing" section.
10.  Create the minimal set of snapshots that are not ancestors of each other. Note that there could still be just a single snapshot in this set ("everyone's descendant") if there was no exit on the previous step because the log file is non-empty.
11.  Combine all entries from this set of snapshots and the log, resolving conflicts and discarding corrupted entries: see "Entry Conflict Resolution and Integrity Checking" below. Result: a "combined" set of entries.
12.  Call the cleanup strategy on the combined set of entries and remove the entries from the "combined" set with execution keys appearing in the collection that is returned by the cleanup strategy. Result: a "cleaned" set of entries.
13.  Truncate the entry log file (if it wasn't empty already), leaving only the `[header]` table, while holding the `entry_log.lock` in the *exclusive* mode.
14.  If this `FsPersister`'s `use_fresh_object_statuses` is `True`, delete from `fresh_objects/` all files whose names are in the set of object IDs that have been referenced from all non-corrupted entries "seen" in this `FsPersister.cleanup()` so far in all non-corrupted snapshots or in the log, whether they are included in the cleaned set of entries or not (entries were excluded from the cleaned set by the cleanup strategy), *with the exception of the object IDs that have been referenced from entries that have been read from the entry log file and **have** been included in the new snapshot*. See the "Fresh Object Statuses" section below for details.
   *   Since the number of files in `fresh_objects/` is likely much smaller than the number of files we should delete from it (actually, "ensure they are deleted", because most of these files wouldn't be present in this directory), as an optimisation, call `os.listdir(fresh_object_dir)`, then compute the intersection with the list of object names that should be deleted, and then call `os.remove()` only on these files in the intersection.
15.  Determine whether writing a new snapshot file is needed. It's *not* needed if there was a single "everyone's descendant" snapshot on the step 9 above and *all* entries from the entry log were excluded by the cleanup strategy, and the cleanup strategy didn't exclude any entries from "everyone's descendant" snapshot. 
16.  If needed, write a new snapshot file with the cleaned set of entries and the appropriate `[parents]` table, where the parents of this new snapshot are the "minimal set" from the step 9 above. For snapshot file writing, use the procedure "Atomic File Writes" described below. Also, after this step is successful, put the dict with the new mapping from execution keys to `EntryMetadata` objects in a field of this `FsPersister`, making it the new "live" set of entries tracked by this `FsPersister` and available (under `threading.Lock`) to other `FsPersister` methods such as `get()` and `put()`.
17.  Delete from `entry_snapshots/` all (non-corrupted) snapshot files that were fed into the new snapshot, from the step 6 onwards.
18.  If `cleanup()` is called with `include_content=True` **or** `delete_orphan_objects=True`, do the object cleanup:
   a.   If `delete_orphan_objects=True` prepare a "to_keep" list of objects, otherwise a "to_delete" list of objects. "to_keep" objects are referenced from the entries that are included in the new snapshot. "to_delete" objects are referenced from any non-corrupt entries that have been seen throughout this procedure and are *not* referenced from the entries that are included in the new snapshot.
   b.   With the "to_keep" list of objects, list all files in `objects/` and delete all that don't appear in the "to_keep" list and that *don't* have a corresponding marker file in the `fresh_objects/` directory, if fresh objects statuses are used by this `FsPersister`. With the "to_delete" list, try to delete objects from this list directly.
19.  Release `modification.lock`.
20.  Release `objects.lock` if acquired in the step 4 above.

This procedure is designed to be resilient to the Marimo process termination at any step. The lock files (`objects.lock`, `modification.lock`, and `entry_log.lock`) are unlocked automatically if the process that holds the lock is terminated. The only "garbage" that might be left behind is a temporary file (from atomic writing of the snapshot file, if the current Marimo process is terminated in the middle of that step). It could be cleaned up later via some marimo CLI command or manually.

#### 3.8. Entry Conflict Resolution and Integrity Checking

This section describes various entry ans shanpshot conflict edge cases and integrity checks that are used in `FsPersister`.

**Execution Key Clashes:** It's possible, althrough exceedingly unlikely, that two entries with the same `ExecutionKey` are created by different Marimo processes with the same `block_id`, `module_hash`, and `created_at` (a millisecond-precision `datetime`). `FsPersister.put()` doesn't persist the entry and raises `ExecutionKeyClash`, as per `Persister.put()` specification (see above). When clashing execution keys appear when `FsPersister` merges snapshots that have been synchronized from other machines, `FsPersister` chooses the entry with the largest content sizes (in the alphabetical order of content kinds: `output`, `stderr`, `variables`; absent content kind is assumed to have zero size). If all content sizes are equal, all other entry metadata are compared in the "Mapping Hashing" order (see below). This deterministic resolution ensures consistent snapshot merging results across different machines.

**Snapshot Integrity Checking:** `FsPersister` checks the integrity of the snapshots on the file system by comparing the value for the `header.snapshot_hash` key with the hash of the rest of snapshot file's content, excluding the `header.snapshot_hash` key itself. If the hashes do not match, the snapshot is considered corrupted (or not fully synched from other machines yet) and ignored during the subsequent steps of the "New Snapshot Creation" procedure.

Note that the snapshot hashes in the file names `{snapshot_hash}.toml` are *not* used as definitive sources of the snapshot hash: they can be affected by external synchronization systems that may rename files to avoid file conflicts. `FsPersister.cleanup()` "fixes up" the names if it founds two or more files in `entry_snapshots/` that have the same `header.snapshot_hash`, one or more of them *passes* this integrity check, but the file name `{snapshot_hash}.toml` is occupied by another snapshot that *doesn't* pass this integrity check.

For the snapshot hashing procedure, see the "Mapping Hashing" section below.

**Entry Integrity Checking:** `FsPersister` checks the integrity of the entries on the file system by comparing the value for the `hash` key in the entry table with the hash of the rest of this TOML table, excluding the `hash` key itself. If the hashes do not match, the entry is considered corrupted and is discarded during `FsPersister.cleanup()`. For the entry hashing procedure, see the "Mapping Hashing" section below. The most likely source of a corrupt entry is a "torn write" into the entry log file if the machine lost power while that file write was in progress.

If the entry metadata appears corrupt in a snapshot file, but the snapshot hash still matches up with the entry hash (which means that the entry hash itself is correct), that entry is discarded but other entries in the snapshot are *not* discarded.

`FsPersister` "bottoms out" all integrity checks and comparisons when the hashes (either for entries, snapshots, or objects: see "Object IDs" below) collide. Hash collisions are deemed too improbable to justify complicating logic to deal with them.

#### 3.9. Mapping Hashing

Mapping hashing is used both to obtain *entry hashes* and *snapshot hashes*. It's a generic hash
of an arbitrarily nested mapping of mappings and sequences, such as encoded by the whole TOML file (snapshot) or a specific entry table.

For the entry:
```toml
[abcdefghijklmnopqrstuvwxyzABCDEF123456789-_.abcdefghijklmnopqrstuvwxyzABCDEFGH123456789.63875925237555]
variables = { id = "123456789-_abcdefghijklmnopqrstuvwxyzABCDEF", size = 123, format = "pickle" }
hash = "mIG4wyNQHrw"
```
The **entry hash** is effectively computed as:
```python
from base64 import urlsafe_b64encode
from hashlib import sha256

x = sha256()
# Execution key
x.update(block_id.encode())
x.update(module_hash.encode())
x.update(created_at_millis.encode())
# Variables
x.update(b"variables")
x.update(b"format")
x.update(b"pickle")
x.update(b"id")
x.update(object_id.encode())
x.update(b"size")
x.update(str(variables.size).encode()) # b"123"

# Use first 64 bits of sha256 digest.
# Strip the pad `=` character from base64url-encoded string.
hash = urlsafe_b64encode(x.digest()[:8])[:-1]
```

Using only the first 8 bytes (64 bits) of the hash digest because entry hashes are not used for collision resolution or identification (they may clash even within the same snapshot), only for integrity checking. In base64url encoding, the resulting hash is an 11-character string.

Note the alphabetical order of keys in the inline table for `variables`: `format`, `id`, `size`.

When more content kinds are supported on the entry level (`output` and `stderr` are planned), they are also sorted alphabetically before appending to the xxHash stream: `output`, `stderr`, `variables`.

The same "sorted maps" principle is used to compute the **snapshot hash**. Some other details are different:
*   The whole SHA-256 digest is used (32 bytes), rather than only the first 8 bytes as for entry hashes. The base64url-encoded result is a 43-character string.
*   Instead of hashing all nested entry metadata again, entry hashes themselves are used (in their 11-character base64url-encoded form). This sometimes permits discarding corrupted entries in a snapshot file without scrapping the rest of the snapshot: see the description of *entry integrity checking* above.
 
Consider that in TOML, execution keys [block_id.module_hash.created_at] is a compressed notation for nested mappings like:
```python
{block_id: {module_hash: {created_at: b"mIG4wyNQHrw"}}}
```
Rather than:
```python
{f"{block_id}.{module_hash}.{created_at}": ...}
```

The `[header]` table (except for the `snapshot_hash` key) and the `[parents]` table are also fed into the snapshot hash. So, the full mapping that is being hashed is something like:
```python
[
    # The first parts of the execution keys, block_ids (which are considered top-level TOML tables)
    # are sorted *together* with "special" top-level tables: "header" and "parents", so they
    # may appear to be "mixed in between" block_ids.
    ("abcdefghijklmnopqrstuvwxyzABCDEF123456789-_", [
        # module_hash
        ("-abcdefghijklmnopqrstuvwxyzABCDEF123456789_-", [
            # created_at_millis, entry_hash
            ("63875925237555", "mIG4wyNQHrw"),
            ...
        ]),
        ...
    ]),
    ...
    ("header", [
        ("entry_table_name_parts", ["block_id", "module_hash", "created_at"]),
        ("version", "1")
        # No "snapshot_hash" key!
    ]),
    ...
    ("parents", [
        ("abcdef1234567890abcdef1234567890", [...]),
        ...
    ]),
    ...
    # Another block_id table
    ("zbcdefghijklmnopqrstuvwxyzABCDEF123456789-_", ...),
]
```

When hashing list values (such as in `[parents]`; `referenced_objects` list within `variables` content metadata is also considered for advanced deduplication), the list elements are appended in order, without prefix, suffix, or separators. List elements are not sorted by this hashing algorithm. Entry table and snapshot writers must sort the elements themselves when these list values have set semantics, as is the case with `[parents]`, to ensure consistency. The `entry_table_name_parts` list is not stored because it has ordered list semantics, not set semantics.

**Alternatives considered:** considered using [xxHash](https://github.com/ifduyue/python-xxhash) for entry hashes because the overhead of xxHash for small sequences is significantly lower than that of SHA256, and the snapshot loading may require `FsPersister` to do thousands of checks. However, this would defy the purpose of using a secure hashing algorithm at the snapshot level because an attacker would be able to "sneak" a bad object via an entry hash collision, whereas the snapshot hash would still be valid. It's not yet clear whether security considerations for `FsPersister` are at all relevant. If they aren't and entry hashing becomes a bottleneck in some use cases, we can add a configuration option at the persistence directory level (in `config.toml`) to use xxHash for entry hashes instead.

#### 3.10. Object IDs

In the **deduplication mode** (default), object IDs (and hence the file names) are just the *object hashes* of the corresponding objects. As the name of this mode suggests, this mode enables deduplication of contents (stored as objects) across entries.

Since execution of the same block (`mo.persistent_cache()`) at different times create separate entries, and it's plausible that these executions produce byte-identical `variables` (despite different variable dependencies, which would indicate that the block is indifferent to the values of these dependencies, although the Marimo runtime doesn't and couldn't know that). So, objects are expected to be actually deduplicated in the majority of "normal" uses of Marimo's persistence subsystem, not just in rare cases.

The **object hash** is a base64url encoding (without `=` pad at the end) of the **SHA-256 hash** of this object's byte sequence. The result is a 43-character string.

**Alternatives considered:** considered 128-bit xxHash as the object hash. The throughput difference between xxHash and SHA-256 may being to matter when dealing with giant objects, such as multi-gigabyte dataframes. Decided to use SHA-256 following the principle of choosing the secure options by default unless there is a good argument or need to do otherwise. By this principle, using 128-bit xxHash would be a premature optimization. However, an option to use 128-bit xxHash for object hashes (or another hash function) could be added to this persistence directory's `config.toml` in the future.
*   Git also uses SHA-256 as object hashes and IDs (as a more "modern" option; originally, and still supported, Git used SHA-1), but compatibility with Git is *not* a factor because Marimo persistence subsystem's objects are not valid Git object anyways: Marimo persistence subsystem's object (files) don't have any *header*, they start directly with the byte sequence (serialized content), whereas Git's object have Git-specific headers.

**Execution key-qualified mode:** object IDs (and hence the names of the object files) include parts of the execution key: `{object_hash}.{module_hash}.{created_at}`, where `module_hash` and `created_at` are represented in the same way as in entry snapshot and log files (see "Snapshot File Format (TOML)" above): base64url-encoded and `create_at_millis()`, respectively. An example of an execution key-qualified object ID:
```
123456789-_abcdefghijklmnopqrstuvwxyzABCDEF.abcdefghijklmnopqrstuvwxyzABCDEF123456789_-.63875925237555
```

Execution key-qualified mode prevents a certain type of conflict between *object cleanup* and non-cooperative synchronization mechanisms like Dropbox. See the section "Object Cleanup" below for more details.

Regardless of the mode, **object hashes are computed in memory**, in a streaming fashion, while the object's bytes hit the disk to prevent any possible bit rot or corruption issues.

### 3.11. `objects/` Directory

All object files are stored in a single, flat `objects/` subdirectory of the persistence directory:
```
__marimo__/
  persist/
    objects/
      123456789-_abcdefghijklmnopqrstuvwxyzABCDEF
      123456789-_abcdefghijklmnopqrstuvwxyzABCDEF.abcdefghijklmnopqrstuvwxyzABCDEF123456789_-.63875925237555
      ...
```

As discussed in the "Persistence Directory Config" section above, objects with IDs in different modes might potentially be mixed in this directory.

`variables` contents are currently serialised (using Pickle or JSON) as a single `dict`, mapping from persisted block's top-level variable names to the values, that produces a single serialized byte sequence, i.e., a single *content object*. This already permits some Pickle-native deduplication when some large objects are referenced from within multiple variables in that `dict`.

Using Pickle's [out-of-band buffers](https://docs.python.org/3/library/pickle.html#out-of-band-buffers) and [persistend object references](https://docs.python.org/3/library/pickle.html#persistence-of-external-objects) to deduplicate serialised variables more thoroughly (such as if multiple blocks or cells serialise different variables that thinly wrap the same large dataframe) is out of scope for the initial implementation, but if/when it's added in the future, these "extracted" objects will be stored as separate files in the same `objects/` directory (also shared with `output` and `stderr` objects, by the way), and there would be no way to "correlate" these objects other than through consulting the entry metadata that is stored separately. This paragraph is an elaborate way of saying that the `objects/` directory doesn't have any semantic grouping (such as via subdirectories or file naming) on the file system level.

Object files are written *atomically*, as described in the "Atomic File Writes" section below.

The way `FsPersister` identifies and stores objects may resemble the [Git object database](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects) (and the term "object" is definitely taken from Git), but there are many differences in details:
*   **`FsPersister`'s object files don't include any header:** the whole of the object file is just the serialized byte sequence. Git's objects have Git-specific headers.
*   **A *flat* `objects/`directory.** Git groups object files into prefix folders: `00/123...` where `00` are the first 2 characters in Git object's (hex-encoded) ID. Git does this in the name of [scalability](https://softwareengineering.stackexchange.com/questions/301400). If `FsPersister`'s flat directory approach will not be sufficient in some use cases (although this seems unlikely), a configuration option might be added to Marimo's persistence directory's `config.toml` to enable prefix grouping similar to Git.
*   **`FsPersister`'s object IDs are (or include) base64url-encoded hashes,** while Git object IDs are hex-encoded. It seems that Git chose hex encoded to support ancient (already around the time when Git was developed, i.e., 20 years ago) file systems that don't support case-sensitive file names. `FsPersister` clearly doesn't have this limitation, so it uses a more compact base64url encoding.
*   **`FsPersister`'s objects are not compressed on the file system.** Git compresses object by default, and although it has an option to disable compression, it's obscure and nobody ever uses it. It seems that Marimo's persistence subsystem could be used more *dynamically* and therefore the `Persister.put()` and `Persister.get()` lantencies are more sensitive, and therefore compression is less attractive. This may become even more salient when/if unpickling of large dataframes is enabled as memory mapping of the range of the object file, without byte sequence copying.

#### 3.11.1. Trivial Objects

`FsPersister` recognises certain "trivial" objects and avoids the whole process of serializing, storing them in files, hashing, cleaning up, etc., and instead directly uses their pre-computed object hashes.

Trivial object IDs don't need to be execution key-qualified and are not recorded as such in entry metadata even if the `FsPersister` is configured to use execution key-qualified object IDs.

Currently, there are two trivial objects:
*   `b'\x80\x04}\x94.'`, the result of Pickle serialization of an empty `variables` dict, `{}`. The object ID is `kmJI5S0fpTLDF-N9ok7WUq5kEQ-CGcteBhZovTCR8Eg`.
*   `b'{}'` - the JSON serialization of the empty `variables` dict. The object ID is `RBNvo1WzZ4oRRq0W9-hknpT7T8If536DEMBg9hyq_4o`.

When `output` and `stderr` content kinds are supported in the persistence subsystem, trivial objects should also include the empty byte sequence (object ID: `47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU`), the outputs of sole `mo.md("")` and `mo.md("\n")` calls, and the outputs that are the result of a single [`mo.output.append(value)`](https://docs.marimo.io/api/outputs/#cell-outputs) call where the value is either `None`, `True`, `False`, `""`, `"\n"`, `{}`, `[]`, `set()`, `0`, `1`, or `float('nan')`.

The main purpose of special handling of trivial objects is not optimization but preventing "trivial" deduplication to conflict with object cleanup: see the section "Object Cleanup" below.

### 3.12. Entry Writing

The **`FsPersister.put()` algorithm:**
1.   Serialize (using Pickle or JSON) the `Entry`'s contents (currently, only `variables`) into file(s) in `__marimo__/temp/` directory. See the justification for using this directory in the "Atomic File Writing" section below. Hash the serialized byte sequence in parallel with file writing, in a streaming way: streaming enables hashing objects larger than Marimo's process memory. Result: one or more files in `__marimo__/temp/` and their hashes.
   *   If/when deep object deduplication based on Pickle's [persistend object references](https://docs.python.org/3/library/pickle.html#persistence-of-external-objects) and [out-of-band buffers](https://docs.python.org/3/library/pickle.html#out-of-band-buffers) is implemented, the [`Pickler`](https://docs.python.org/3/library/pickle.html#pickle.Pickler) subclass that `FsPersister` uses might know that an object will be deduplicated without writing it to `__marimo__/temp/`. Specifically, it will maintain a [weak ref dictionary](https://docs.python.org/3.13/library/weakref.html#example) for serialized Python objects that a serialized into a dedicated (Marimo persistence subsystem's) "content object". The keys in that `WeakValueDictionary` are `TwoIds` objects that use only `self.python_id = id(obj)` for `__eq__()` and `__hash__()`, but also have a "payload" `self.persistence_id = object_id` field.
   *   Before deciding that serialization into `__marimo__/temp/` can be skipped altogether, `FsPersister` attempts to acquire `objects.lock` in the *shared* mode. This is needed to prevent race with object cleanup potentially executed by a concurrent `marimo` process. If a non-blocking lock acquisition attempt fails, fall back to serializing the content (which doesn't require the lock): a concurrent object cleanup might take a longer time than content serialization.
   *   If after all entry contents are serialized there are *no* objects whose serialization was skipped, release `objects.lock` so that `fsync` of objects (next step) happens while the lock is not held.
2.   `fsync` the object files in `__marimo__/temp/`.
3.   Prepare the new entry metadata.
4.   Acquire `modification.lock` in the *exclusive* mode. This ensures that at most one marimo process can append the entry log file at any time (and truncate it, which is done in the "New Snapshot Creation" procedure also with `modification.lock` held), preventing races on the file size: see the section "Per-Machine Entry Log" above.
   *   This acquisition is attempted with a timeout of 5 seconds. If not successful, `FsPersister.put()` releases `objects.lock` if needed, deletes the files from `__marimo__/temp/` if needed and returns `None` (note: the return type of `Persister.put()` is `Optional[EntryMetadata]`), indicating a "temporary unavailability" of this persistence directory, as per `Persister.put()` documentation. This may happen if two separate `marimo` processes call to `FsPersister.put()` when accessing the same persistence directory at the same time, and one of them takes a long time to complete. Marimo core (the `mo.persistent_cache()` logic) can handle this by re-trying `put()` after some time. Then if `put()` returns `None` again, the Marimo UI should notify the user about this. Perpetual inability to acquire the lock indicates an issue that requires user's intervention: perhaps a "rogue" (non-marimo) process holds a lock on the `modification.lock` file.
5.   Re-load entries from the log file as described in the "Log Monitoring and Re-Loading" section above.
6.   If the entry's execution key is already known to this `FsPersister`, and the entry metadata match with what is prepared on the previous step, return this entry metadata and exit the procedure. If they don't match, then release the lock(s), delete the files from `__marimo__/temp/` if needed and raise an `ExecutionKeyClash` exception.
7.   Append the entry metadata to the entry log file.
8.   If log-file-based trigger conditions for entry log merge are met (see the "Per-Machine Entry Log" section above): the number of entries or the age of the oldest entry in the log, escalate to "New Snapshot Creation" via calling `FsPersister.cleanup()`. Some details of such a `cleanup()` call are different, given that we already hold `modification.lock` and the log file contents are already known because they have been re-loaded just above. `cleanup()` discerns that it's called from `put()` by the presence of `log_entries: list[EntryMetadata]` keyword argument. If the snapshot created by this `cleanup()` *doesn't* include the entry metadata we have just written within this `put()` procedure (this is highly unusual, but is considered valid), delete the files from `__marimo__/temp/` if needed and skip to the step 11 below.
9.   If *object fresh statuses* are used by this `FsPersister`, create marker files (empty files, *not* symlinks) in `fresh_objects/`. These marker file names are the IDs of *all* objects referenced from the new entry, whether they are going to be newly created in the `objects/` directory (in the following step) or already existed in `objects/` and were deduplicated. If the marker files for some of these objects already exist, they can be skipped, updating `mtime` via `os.utime()` is *not* needed. See the "Fresh Object Statuses" section below for more details.
10.  `os.replace()` the object files from `__marimo__/temp/` into this persistence directory's `objects/` subdirectory.
11.  Release `modification.lock`.
12.  Release `objects.lock` if it is still held (beginning from the step 1 above).
13.  If the new entry has been appended to the log file as the *first* one, and `FsPersister.cleanup()` was *not* called in the step 8 above, and this `FsPersister` is configured with a positive `entry_merge_timeout_seconds` value, create a timer in the background to call for `FsPersister.cleanup()` after the configured timeout.
14.  Return the entry metadata from `put()` as `EntryMetadata`.

Note that the entry log file, the `fresh_objects/` and `objects/` directories are not `fsync`-ed because durability of entry contents is not guaranteed by `FsPersister` (see the desiderata in the first message of [#3176](https://github.com/marimo-team/marimo/issues/3176)).
*   The entry log file appends are tiny and therefore are very unlikely to be corrupted in the case of a sudden power loss of a machine.
*   If the object files don't appear in the `objects/` directory because of a power loss, `FsPersister.get()` will treat as invalid the entry pointing to these objects (the entry itself may survive a power loss in the entry log file or a snapshot) and will try to retrieve an earlier entry (if applicable). See also the "Object Cleanup" section where another reason is given for this resilient treatment of missing objects.
*   If file system's operations are reordered and a machine crash occurs in such a moment that objects in `objects/` survive the crash but marker files in `fresh_objects/` don't, this will make these objects appear "not fresh", but it's fine because fresh object statuses themselves are used to prevent rather unlikely object deletions due to interference with non-cooperative synchronization systems. Given the extremely low chance that such a machine crash occurs, it's not worth it to `fsync` the `fresh_objects/` directory.
*   `fsync`-ing the object files themselves is not needed strictly speaking, but we do it because large object writes are more likely to be corrupted during a power loss than entry log file appends and directory changes. Also, object files are usually `fsync`-ed while `modification.lock` is *not* held, so there are no concurrency implications of the latency of this `fsync`.

### 3.13. Object Cleanup

The simplest approach to object cleanup is to delete from the `objects/` directory the objects that are referenced by the entries that have been cleaned up in the `FsPersister.cleanup()` and that are not referenced from any of the remaining entries.

This approach is fine if at least one of the following conditions are met:
*   The persistence directory is *not* synchronized across machines at all.
*   A *cooperative* synchronization system is used to manage the object in the `objects/` directory, such as Git, git-annex, Datalad, DVC, etc: see the section "External Synchronization" above.
*   The persistence directory is synchronized across machines, but there is a single "writer" machine on which the writes to the persistence directory happen exclusively.
*   There are multiple "active" machines that may have `marimo` processes writing to their persistence directories at the same time, but they always work on *different notebooks that couldn't plausibly produce identical contents* (and, therefore, deduplicate objects): for example, teammates working in the same project on separate notebooks. Note that asserting that different notebooks will not produce identical contents is easier when only explicit `mo.persistence_cache()` context blocks are used. When *all* cells in the notebooks are persisted automatically (see [#3054](https://github.com/marimo-team/marimo/issues/3054)), cells across notebooks may persist trivial `variables` dicts like `{}`. However, the special handling of such trivial objects (see the "Trivial Objects" section above) should prevent almost all such conflicts, unless the notebooks are actually somewhat related and can produce non-trivial identical contents.
*   The persistence directory is synchronized between multiple "active" machines, but there is only one active at any single time, and the internet speed and the sizes of objects are such that synchronization systems always have ample time to complete the synchronization between the working sessions on these different machines. A typical example of this would be a solo user synchronizing between their laptop and a PC, while never actively "coding in Marimo" (or their AI agent coding on their behalf) on both machines at any time. This condition also requires that `FsPersister()` is configured with `cleanup_on_exit=True` argument (or `fs_persister.defaults.cleanup_on_exit=true` in `.marimo.toml`) and it is working, i.e., Marimo processes are exiting "cleanly" rather than via SIGKILL.

If any of the above conditions is true, the user should configure `use_fresh_object_statuses=False`, `cleanup_default_include_content=True` and `cleanup_default_delete_orphan_objects=False` in the `FsPersister()` constructor, or alternatively `use_fresh_object_statuses=false`, `cleanup_default_include_content=true` and `cleanup_default_delete_orphan_objects=false` in the `[fs_persister.defaults]` table in [`.marimo.toml` or `pyproject.toml`](https://docs.marimo.io/guides/configuration/#user-configuration-file) to enable the simple cleanup approach (the default values for these three configuration knobs are all opposite from the values given above).

When none of the conditions listed above is met, the following race scenario between Marimo processes and non-coooperative synchronization is possible with the simple object cleanup approach described above:
1. On machine A, the entry is deleted that references object X. The object X is deleted from the `objects/` directory on machine A.
2. On machine B, a new entry is created that also references the object X (due to deduplication), that is still present in the `objects/` directory on machine B.
3. The *deletion* of the object X is synchronized from machine A to machine B, i.e., the external, non-cooperative synchronization system deletes the object X from the `objects/` directory on machine B.
4. As a result, on machine B there will be a "live" persisted entry (created recently and not yet eligible for cleanup itself) that references the object that no longer exists on any machine.

Here're the approaches to mitigate such a race:
*   **Explicit Object Cleanup:** By default, `FsPersister.cleanup()` (also when called from `FsPersister.put()` or `FsPersister.on_exit()`) does *not* cleanup the content (i.e., objects). To clean up the objects, the user should run a command `marimo persist cleanup --include_content`. When running this CLI command, the user is responsible for ensuring that concurrent notebook execution is *not* happening on other machines that may lead to a race scenario described above.
   *   For this to actually cleaning up most of the objects, *deleting orphan objects should be turned on* (which is also the default). However, this exposes the cleanup to another race scenario, which is described below, and which is mitigated by "Fresh Object Statuses".
*   **Use a *cooperative* synchronization system** such as git, git-annex, DVC, etc.: see more details in the "External Synchronization" section above. With a cooperative synchronization system, use `use_fresh_object_statuses=False`, `cleanup_default_include_content=True` and `cleanup_default_delete_orphan_objects=False` configurations (see above).
*   **Disable Content Deduplication via using `ContentStore`'s _execution key-qualified mode_.** The obvious tradeoff is losing the benefits of content deduplication. The configuration options to choose this path are `object_id_mode="execution_key_qualified"`, `use_fresh_object_statuses=False`, `cleanup_default_include_content=True` and `cleanup_default_delete_orphan_objects=False`.
   *  Note: it's not clear (at least I cannot prove this in the abstract) that this approach couldn't lead to the appearance and accumulation of *orphan objects*. Disabling content deduplication while using `cleanup_default_delete_orphan_objects=True` (the default), or passing `delete_orphan_objects=True` explicitly into `FsPersister.cleanup()`, or running a command `marimo persist cleanup --delete_orphan_objects` **is exposed to another race scenario**, described below.
*   **Grace Period:**  When an object is deleted using a "simple" cleanup approach described above, it's merely marked for deletion in an "object metadata store" (which can be implemented as SQLite, and it could be the same SQLite db that is used for storing small content objects, as mentioned in the section "Scope" above as one of the possible future improvements of the persistence subsystem). The object file itself is not actually deleted for a configurable grace period (e.g., 1 week) to allow the deletion metadata to be synchronized to other machines.
   *   This approach is not implemented at this moment because SQLite for storing object metadata and small objects is not introduced yet.
   *   Note that this approach is different from Git's own "grace period-like" protections in `git gc` (see [here](https://stackoverflow.com/a/37734293) for details). Fundamentally, the grace period doesn't solve the issue because the step 2 in the race scenario above could happen at an arbitrary time (at least not in arbitrary use cases of Marimo). However, in use cases where there *is* a very strong "recency bias" in what comes to persisted block results and deduplication, object cleanup with grace period will be effective.

In addition to all of the above approaches, **ignoring broken object references in entries** is employed as a universal robustness measure. If the object file that is referenced from an entry is missing in the `objects/` directory, `FsPersister.get()` returns an older entry (if `exact_match_created_at=False`) or returns `None` if there is no older entry, instead of raising an error. The caller of `FsPersister.get()` such as `mo.persistent_cache()` will then re-execute the persisted block and will store the new entry via `FsPersister.put()`. This is generally a good resilience practice for `FsPersister` because non-cooperative synchronization systems are not guaranteed to sync the objects before the entry snapshots even in "normal" scenarios, let alone the races like described above.

#### 3.13.1. Orphan Object Cleanup Race Scenario

When `FsPersister.cleanup()` with `delete_orphan_objects=True` is called, such as in the *explicit object cleanup* approach (which is the default), the following race scenario is possible:

1. On machine A, `FsPersister.put()` creates an object that is immediately synced by the synchronization system to machine B (before the corresponding metadata entry has landed in any snapshot, and that snapshot has been synced).
2. On machine B, `FsPersister.cleanup(delete_orphan_objects=True)` deletes this object as an "orphan".
3. This deletion is picked up by the synchronization system and is "synced back" to machine A, leading to the deletion of this content object on machine A.

This race *doesn't* require extremely unfortunate timing to happen because the period between an object is written in `FsPersister.put()` and when this object is referenced from an entry in the new *snapshot* (rather than the entry log file) can be large: the entry log file merge might not be triggered for a long time: see the "Per-Machine Entry Log" section.

#### 3.13.2. Fresh Object Statuses

The orphan object cleanup race scenario could be mitigated with the usage of **fresh status marker files** for object. Albeit this mitigation approach doesn't provide a hard guarantee that this race doesn't happen, this race scenario would require extremely unfortunate timing and implausible even sequencing to happen when fresh object statuses are used.

The specific operations with fresh status marker files are already described as parts of "New Snapshot Creation" and "Entry Writing" procedures. This is how it works:
*   `FsPersister.put()` writes the marker files to the `fresh_objects/` directory **before** it moves the object files itself into the `objects/` directory. Non-cooperative synchronization systems like Dropbox usually prioritise syncing smaller files before larger files. Since these marker files also appear in the persistence directory earlier than the object files themselves, and they are smaller (they have size of zero; note that the marker files are *not* symlinks, they correspond to the object files via sharing the name, i.e., the object ID), it's almost certain that non-cooperative synchronization systems will sync the marker files to other machines earlier than the corresponding object files.
*   When `FsPersister.cleanup()` deletes orphan objects by listing the files in `objects/` and deleting all files except those in a "to_keep" list, it *skips* the files that have "fresh" status markers in `fresh_objects/`.
*   `FsPersister.cleanup()` deletes all "fresh" markers for all objects that have been referenced from entries in the snapshots (whether they were included in the latest snapshot by the cleanup strategy or not), but except for those objects that have been referenced from the entries in the entry log. In effect, the objects should retain the fresh status when an entry referencing them is merged from the log file to the new snapshot file. The fresh status for the object is deleted only during the *next, subsequent* call to `FsPersister.cleanup()`, unless new entries have been added to the entry log that also reference this object.
*   After the new snapshot is created that includes the entry referencing the object and a *subsequent* call to `FsPersister.cleanup()` that may stip the object's fresh status, external synchronization system should already sync that snapshot file to other machines on which cleanup with `delete_orphan_objects=True` might be called. And as soon as the snapshot is synced, the object wouldn't be seen as orphan. In theory, it's possible that the subsequent call to `FsPersister.cleanup()` happens immediately after that snapshot-creating call, and deletions of the fresh status markers done in the subsequent `cleanup()` are *still* synched earlier than the snapshot created in the previous `cleanup()` call, but this doesn't seem realistic.

### 3.14. Atomic File Writes

Atomic file writes are used for writing new snapshot files in the "New Snapshot Creation" procedure in `FsPersister.cleanup()` to "install" files that are meant to be synchronized to other machines with external synchronization systems.

This is needed to prevent interferences when the synchronization system creates the snapshot file at the same name right at the time the metadata store is writing the snapshot to the file.

Writing object files (as described in the "Entry Writing" section) also follows the atomic file writing algorithm, but the steps of this algorithm are interleaved with other actions done in `FsPersister.put()`. 

In the case of objects, the additional purpose of atomic file writing is to permit *streaming hashing* (see the "Object IDs" section above) while writing out the object to a temporary file and *not* requiring the whole object to reside in memory: if the `variables` references a memory-mapped dataframe, the content object could be too large to fit into memory. Directly streaming the object to `objects/` directory is not possible because the name of the file (object ID) depends on the hash.

**The Atomic File Writing Procedure:**
1. Write to a *temp* file in `__marimo__/temp/`. Use this location instead of `tempfile.gettempdir()` because the latter is not guaranteed to be mounted on the same file system as `__marimo__/persist/` (this is a prerequisite for calling `os.replace()` later). On the other hand, making the temp file location dependent on the local fs mounting seems unnecessarily "jittery".
2. `fsync` the temp file, or `fcntl(F_FULLSYNC)` if available, [cf. `atomicwrites`](https://github.com/untitaker/python-atomicwrites/blob/master/atomicwrites/__init__.py#L39-L44).
3. `os.replace()` the temp file to the target filename in the target directory: `entry_snapshots/` for snapshot files, `objects/` for object files.

### 3.15. Threading, Asynchrony and Intra-Process Locking

Apart from inter-process, file-based locks (see the "Locks" section) `FsPersister` has a `state_lock: threading.Lock` field to guard access and modification to its state, including:
*   The mapping of "live" execution keys to `EntryMetadata`.
*   The name (snapshot hash) of the latest loaded or created snapshot by this `FsPersister`.
*   The state of the latest entry log file parsing, done either from the background thread (see "Log Monitoring and Re-Loading"), `FsPersister.put()` or `FsPersister.cleanup()`. This state includes file offsets to all "definitely well-formed" TOML table headers (see "Per-Machine Entry Log"), names of these tables, texts between the headers (i.e., unparsed texts of TOML tables), and the results of their parsing: a valid header, an `EntryMetadata`, or a parsing error.

Operations guarded by `FsPersister.state_lock` are short, only used to access the state and swap the state objects. The main work of computing new state objects is done while `FsPersister.state_lock` is not held.

`FsPersister` uses `FileWatcher`s from `marimo._utils` to detect changes to both the entry log file and the `entry_snapshots/` directory. Since all changes in the `entry_snapshots/` directory are "atomic" snapshot file movements (see "Atomic File Writes" above) and file deletions, this should be sufficient. `FileWatcher` uses `asyncio` (the event loop) internally.

When these file watchers detect changes, they hand-off entry log re-loading or new snapshot creation tasks to the two dedicated `ThreadPoolExecutor(max_workers=1)` executors, respectively.

## 4. Legacy Support

To ensure backward compatibility with existing cached data, a `LegacyPersister` is provided. This class:

*   Uses the existing `__marimo__/cache` directory.
*   Delegates to the existing `PickleLoader` and `JsonLoader` for serialization and deserialization.
*   Handles the conversion between the new `ExecutionKey` and the cached file naming scheme.
*   Does *not* implement the cleanup mechanism.

## 5. Marimo API Changes

**`App()` Constructor:**  The `App()` constructor now accepts an optional `persister` argument, which should be an instance of a `Persister` subclass.  If no `persister` is provided, the system automatically chooses between `LegacyPersister` if `__marimo__/cache` exists and `FsPersister` if `__marimo__/cache` does not exist. For this purpose, `__marimo__` directory itself should be found first. The first location that is checked is relative to the directory of this notebook file (where the `App()` constructor is called), then relative to the parent of that directory, and so on, recursively. If there is no `__marimo__` directory in any of these directories, the first location is assumed (i.e., directly in the directory of the notebook file), and since `__marimo__` itself is absent in this case, `__marimo__/cache` is also absent, and `FsPersister` is chosen. When this `FsPersister`'s `put()` is called for the first time, `__marimo__` directory will be created with all the sub-directories within it: `temp/` and `persist/` (or another name if provided via `FsPersister(dir_path=...)`).

**`persistent_cache` Decorator:** The `method` argument of the `persistent_cache` decorator is deprecated because it doesn't differentiate between content kinds, that makes little sense when `output` and `stderr` content kinds are added in addition to `variables`. Also, "method" is vague because the whole `Persister` abstraction is also a "method", while "serialisation format" is something some specific and orthogonal to the rest of `Persister` configuration. The replacement for `method` is `content_spec` argument of the `ContentSpec` type, see the API in the section "Persister" above.
