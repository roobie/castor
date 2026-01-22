"""Store verification and inspection utilities."""

import struct
from pathlib import Path
from typing import List, Dict


def verify_store_structure(store_path: Path, algo: str = "blake3-256") -> bool:
    """
    Verify the basic structure of a Castor store.

    Args:
        store_path: Path to the store root
        algo: Expected algorithm name

    Returns:
        True if structure is valid

    Raises:
        AssertionError if structure is invalid
    """
    assert store_path.exists(), f"Store path does not exist: {store_path}"
    assert store_path.is_dir(), f"Store path is not a directory: {store_path}"

    config_file = store_path / "config"
    assert config_file.exists(), "config file missing"

    objects_dir = store_path / "objects" / algo
    assert objects_dir.exists(), f"objects/{algo} directory missing"
    assert objects_dir.is_dir(), f"objects/{algo} is not a directory"

    refs_dir = store_path / "refs"
    assert refs_dir.exists(), "refs directory missing"
    assert refs_dir.is_dir(), "refs is not a directory"

    return True


def get_object_path(store_path: Path, hash_str: str, algo: str = "blake3-256") -> Path:
    """
    Get the filesystem path for an object given its hash.

    Args:
        store_path: Path to the store root
        hash_str: Object hash (hex string)
        algo: Hash algorithm

    Returns:
        Path to the object file
    """
    if len(hash_str) < 2:
        raise ValueError("Hash too short")

    prefix = hash_str[:2]
    rest = hash_str[2:]
    return store_path / "objects" / algo / prefix / rest


def verify_object_exists(store_path: Path, hash_str: str, algo: str = "blake3-256") -> bool:
    """
    Verify that an object exists in the store.

    Args:
        store_path: Path to the store root
        hash_str: Object hash (hex string)
        algo: Hash algorithm

    Returns:
        True if object exists

    Raises:
        AssertionError if object doesn't exist
    """
    obj_path = get_object_path(store_path, hash_str, algo)
    assert obj_path.exists(), f"Object does not exist: {hash_str}"
    assert obj_path.is_file(), f"Object path is not a file: {obj_path}"
    return True


def read_object_header(store_path: Path, hash_str: str, algo: str = "blake3-256") -> Dict:
    """
    Read and parse the header of an object file.

    Args:
        store_path: Path to the store root
        hash_str: Object hash (hex string)
        algo: Hash algorithm

    Returns:
        Dict with keys: magic, version, type, algo_id, payload_len
    """
    obj_path = get_object_path(store_path, hash_str, algo)

    with open(obj_path, "rb") as f:
        header_bytes = f.read(16)
        if len(header_bytes) < 16:
            raise ValueError("Object file too short")

        magic = header_bytes[0:4]
        version = header_bytes[4]
        obj_type = header_bytes[5]
        algo_id = header_bytes[6]
        header_bytes[7]
        payload_len = struct.unpack("<Q", header_bytes[8:16])[0]

        return {
            "magic": magic,
            "version": version,
            "type": obj_type,
            "algo": algo_id,
            "payload_len": payload_len,
        }


def get_object_type(store_path: Path, hash_str: str, algo: str = "blake3-256") -> str:
    """
    Get the type of an object (blob or tree).

    Args:
        store_path: Path to the store root
        hash_str: Object hash (hex string)
        algo: Hash algorithm

    Returns:
        "blob" or "tree"
    """
    header = read_object_header(store_path, hash_str, algo)
    type_id = header["type"]

    if type_id == 1:
        return "blob"
    elif type_id == 2:
        return "tree"
    else:
        raise ValueError(f"Unknown object type: {type_id}")


def read_blob_content(store_path: Path, hash_str: str, algo: str = "blake3-256") -> bytes:
    """
    Read the content of a blob object.

    Args:
        store_path: Path to the store root
        hash_str: Object hash (hex string)
        algo: Hash algorithm

    Returns:
        Blob content as bytes
    """
    obj_path = get_object_path(store_path, hash_str, algo)

    with open(obj_path, "rb") as f:
        # Skip header
        f.seek(16)
        return f.read()


def parse_tree_entries(
    store_path: Path, tree_hash: str, algo: str = "blake3-256"
) -> List[Dict]:
    """
    Parse the entries of a tree object.

    Args:
        store_path: Path to the store root
        tree_hash: Tree object hash (hex string)
        algo: Hash algorithm

    Returns:
        List of dicts with keys: type, mode, hash, name
    """
    obj_path = get_object_path(store_path, tree_hash, algo)

    entries = []
    with open(obj_path, "rb") as f:
        # Skip header
        f.seek(16)

        while True:
            # Read entry type
            type_byte = f.read(1)
            if not type_byte:
                break

            entry_type = struct.unpack("B", type_byte)[0]
            mode = struct.unpack("<I", f.read(4))[0]
            hash_bytes = f.read(32)
            name_len = struct.unpack("B", f.read(1))[0]
            name_bytes = f.read(name_len)

            entries.append({
                "type": "blob" if entry_type == 1 else "tree",
                "mode": mode,
                "hash": hash_bytes.hex(),
                "name": name_bytes.decode("utf-8"),
            })

    return entries


def count_objects(store_path: Path, algo: str = "blake3-256") -> int:
    """
    Count the total number of objects in the store.

    Args:
        store_path: Path to the store root
        algo: Hash algorithm

    Returns:
        Number of objects
    """
    objects_dir = store_path / "objects" / algo
    if not objects_dir.exists():
        return 0

    count = 0
    for prefix_dir in objects_dir.iterdir():
        if prefix_dir.is_dir():
            for obj_file in prefix_dir.iterdir():
                if obj_file.is_file():
                    count += 1

    return count


def list_all_refs(store_path: Path) -> Dict[str, str]:
    """
    List all references in the store.

    Args:
        store_path: Path to the store root

    Returns:
        Dict mapping ref name to hash
    """
    refs_dir = store_path / "refs"
    if not refs_dir.exists():
        return {}

    refs = {}
    for ref_file in refs_dir.iterdir():
        if ref_file.is_file():
            content = ref_file.read_text().strip()
            # Take the last non-empty line
            lines = [line for line in content.split('\n') if line.strip()]
            if lines:
                refs[ref_file.name] = lines[-1]

    return refs


def calculate_expected_hash(content: bytes) -> str:
    """
    Calculate the expected BLAKE3 hash for given content.

    Note: This is a placeholder. The actual implementation should use
    the same hashing library as Castor.

    Args:
        content: Content to hash

    Returns:
        Hex hash string
    """
    # For now, we'll rely on Castor's output for hash verification
    # This could be implemented with python-blake3 if needed
    raise NotImplementedError("Hash calculation not implemented yet")
