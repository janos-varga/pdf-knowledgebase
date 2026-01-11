"""
Folder structure validators for datasheet ingestion pipeline.

Validates folder paths, datasheet folder structure, and file permissions.
"""

import re
from pathlib import Path

# Windows reserved characters in file/folder names
WINDOWS_RESERVED_CHARS = r'[<>:"|?*]'

# Windows reserved filenames
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def validate_folder_path(folder_path: Path) -> tuple[bool, str | None]:
    """
    Validate that a folder path exists and is accessible.

    Args:
        folder_path: Path to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if validation passed
        - error_message: Error description if validation failed, None otherwise
    """
    # Check if path exists
    if not folder_path.exists():
        return False, f"Path does not exist: {folder_path}"

    # Check if it's a directory
    if not folder_path.is_dir():
        return False, f"Path is not a directory: {folder_path}"

    # Check if it's readable
    try:
        list(folder_path.iterdir())
    except PermissionError:
        return False, f"Permission denied: cannot read directory {folder_path}"
    except OSError as e:
        return False, f"OS error accessing directory {folder_path}: {e}"

    # Check for Windows reserved characters in path
    folder_name = folder_path.name
    if re.search(WINDOWS_RESERVED_CHARS, folder_name):
        # Warning, not error - may work on some systems
        return True, None  # Still valid, but log warning separately

    # Check for Windows reserved names
    if folder_name.upper() in WINDOWS_RESERVED_NAMES:
        return False, f"Folder name is Windows reserved: {folder_name}"

    return True, None


def validate_datasheet_folder(
    folder_path: Path,
) -> tuple[bool, str | None, Path | None]:
    """
    Validate that a folder contains exactly one .md file.

    Args:
        folder_path: Path to datasheet folder

    Returns:
        Tuple of (is_valid, error_message, markdown_file_path)
        - is_valid: True if validation passed
        - error_message: Error description if validation failed, None otherwise
        - markdown_file_path: Path to the markdown file if found, None otherwise
    """
    # First validate the folder path itself
    is_valid, error = validate_folder_path(folder_path)
    if not is_valid:
        return False, error, None

    # Find all markdown files
    try:
        md_files = list(folder_path.glob("*.md"))
    except OSError as e:
        return False, f"Error scanning folder {folder_path}: {e}", None

    # Check markdown file count
    if len(md_files) == 0:
        return False, f"No .md file found in folder: {folder_path}", None

    if len(md_files) > 1:
        file_names = ", ".join(f.name for f in md_files)
        return (
            False,
            f"Multiple .md files found in folder {folder_path}: {file_names}",
            None,
        )

    markdown_file = md_files[0]

    # Validate markdown file is readable
    if not markdown_file.is_file():
        return False, f"Markdown path is not a file: {markdown_file}", None

    try:
        # Try to read the file to check permissions
        with markdown_file.open("r", encoding="utf-8") as f:
            f.read(1)  # Read first byte to check readability
    except PermissionError:
        return False, f"Permission denied: cannot read file {markdown_file}", None
    except UnicodeDecodeError:
        return False, f"File is not valid UTF-8: {markdown_file}", None
    except OSError as e:
        return False, f"Error reading file {markdown_file}: {e}", None

    return True, None, markdown_file


def check_special_characters(folder_name: str) -> list[str]:
    """
    Check for special characters that may cause issues on Windows.

    Args:
        folder_name: Name of folder to check

    Returns:
        List of warning messages (empty if no issues)
    """
    warnings = []

    # Check for Windows reserved characters
    if re.search(WINDOWS_RESERVED_CHARS, folder_name):
        found_chars = re.findall(WINDOWS_RESERVED_CHARS, folder_name)
        warnings.append(
            f"Folder name contains Windows reserved characters: {', '.join(set(found_chars))}"
        )

    # Check for leading/trailing spaces (problematic on Windows)
    if folder_name != folder_name.strip():
        warnings.append("Folder name has leading or trailing spaces")

    # Check for trailing dots (problematic on Windows)
    if folder_name.endswith("."):
        warnings.append("Folder name ends with a dot (.)")

    # Check for very long names (Windows MAX_PATH is 260 chars)
    if len(folder_name) > 200:
        warnings.append(f"Folder name is very long ({len(folder_name)} characters)")

    return warnings


def validate_image_path(image_path: Path) -> tuple[bool, str | None]:
    """
    Validate that an image file exists and is accessible.

    Args:
        image_path: Path to image file

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if validation passed
        - error_message: Error description if validation failed, None otherwise
    """
    # Check if path exists
    if not image_path.exists():
        return False, f"Image file does not exist: {image_path}"

    # Check if it's a file
    if not image_path.is_file():
        return False, f"Image path is not a file: {image_path}"

    # Check file extension
    valid_extensions = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".webp"}
    if image_path.suffix.lower() not in valid_extensions:
        return False, f"Invalid image extension: {image_path.suffix}"

    # Check if readable
    try:
        with image_path.open("rb") as f:
            f.read(1)  # Read first byte to check readability
    except PermissionError:
        return False, f"Permission denied: cannot read image {image_path}"
    except OSError as e:
        return False, f"Error reading image {image_path}: {e}"

    return True, None


def discover_datasheets(root_folder: Path) -> list[Path]:
    """
    Discover all datasheet folders in a root directory.

    A datasheet folder is defined as a subfolder containing exactly one .md file.

    Args:
        root_folder: Root directory to scan

    Returns:
        List of valid datasheet folder paths
    """
    datasheet_folders = []

    # Validate root folder
    is_valid, error = validate_folder_path(root_folder)
    if not is_valid:
        raise ValidationError(f"Invalid root folder: {error}")

    # Scan for subfolders
    try:
        for subfolder in root_folder.iterdir():
            if not subfolder.is_dir():
                continue

            # Check if subfolder is a valid datasheet folder
            is_valid, error, md_file = validate_datasheet_folder(subfolder)
            if is_valid:
                datasheet_folders.append(subfolder)

    except PermissionError as e:
        raise ValidationError(f"Permission denied scanning {root_folder}: {e}") from e
    except OSError as e:
        raise ValidationError(f"Error scanning {root_folder}: {e}") from e

    return datasheet_folders
