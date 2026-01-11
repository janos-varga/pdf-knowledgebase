"""
Markdown parsing utilities for datasheet ingestion pipeline.

Provides functions to:
    - Parse markdown files with UTF-8 encoding
    - Resolve relative image paths to absolute Windows paths
    - Extract and validate markdown content
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger("datasheet_ingestion.markdown_parser")


def parse_markdown_file(markdown_path: Path) -> str:
    """
    Parse markdown file with UTF-8 encoding and basic validation.

    Args:
        markdown_path: Absolute path to markdown file

    Returns:
        Parsed markdown content as string

    Raises:
        FileNotFoundError: If markdown file doesn't exist
        UnicodeDecodeError: If file cannot be decoded as UTF-8
        ValueError: If file is empty or invalid
    """
    # Validate file exists
    if not markdown_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

    if not markdown_path.is_file():
        raise ValueError(f"Path is not a file: {markdown_path}")

    # Validate file extension
    if markdown_path.suffix.lower() != ".md":
        logger.warning(f"File extension is not .md: {markdown_path}")

    # Read file with UTF-8 encoding
    try:
        content = markdown_path.read_text(encoding="utf-8")
        logger.debug(f"Successfully read markdown file: {markdown_path}")
    except UnicodeDecodeError as e:
        logger.error(f"Failed to decode markdown file as UTF-8: {markdown_path}")
        raise UnicodeDecodeError(
            e.encoding,
            e.object,
            e.start,
            e.end,
            f"Cannot decode {markdown_path} as UTF-8: {e.reason}",
        ) from e

    # Validate content is not empty
    if not content.strip():
        raise ValueError(f"Markdown file is empty: {markdown_path}")

    logger.info(
        f"Parsed markdown file: {markdown_path.name} ({len(content)} characters)"
    )

    return content


def resolve_image_path(
    image_ref: str,
    markdown_path: Path,
    folder_path: Path,
) -> Path | None:
    """
    Resolve relative image path to absolute Windows path.

    Handles common markdown image reference formats:
        - ![alt](images/photo.png)
        - ![alt](./images/photo.png)
        - ![alt](../images/photo.png)
        - ![alt](/absolute/path/photo.png)

    Args:
        image_ref: Image reference from markdown (relative or absolute)
        markdown_path: Absolute path to markdown file
        folder_path: Absolute path to datasheet folder

    Returns:
        Absolute path to image file, or None if resolution fails

    Examples:
        >>> resolve_image_path("images/pinout.png",
        ...     Path("D:/datasheets/TL072/TL072.md"),
        ...     Path("D:/datasheets/TL072"))
        WindowsPath('D:/datasheets/TL072/images/pinout.png')
    """
    # Handle empty references
    if not image_ref:
        logger.warning("Empty image reference provided")
        return None

    # Remove URL encoding if present (e.g., %20 for spaces)
    image_ref = image_ref.replace("%20", " ")

    # Convert to Path object
    image_path = Path(image_ref)

    # If already absolute path, validate and return
    if image_path.is_absolute():
        if image_path.exists():
            logger.debug(f"Resolved absolute image path: {image_path}")
            return image_path
        else:
            logger.warning(f"Absolute image path does not exist: {image_path}")
            return None

    # Resolve relative path from markdown file location
    try:
        # Try resolving relative to markdown file's directory
        markdown_dir = markdown_path.parent
        resolved_path = (markdown_dir / image_path).resolve()

        if resolved_path.exists():
            logger.debug(f"Resolved image path relative to markdown: {resolved_path}")
            return resolved_path

        # Try resolving relative to datasheet folder root
        resolved_path = (folder_path / image_path).resolve()

        if resolved_path.exists():
            logger.debug(
                f"Resolved image path relative to folder root: {resolved_path}"
            )
            return resolved_path

        # Image path doesn't exist
        logger.warning(
            f"Image path '{image_ref}' does not exist "
            f"(tried relative to markdown and folder root)"
        )
        return None

    except (OSError, ValueError) as e:
        logger.error(f"Error resolving image path '{image_ref}': {e}")
        return None


def extract_image_references(content: str) -> list[str]:
    """
    Extract all image references from markdown content.

    Supports standard markdown image syntax:
        - ![alt text](path/to/image.png)
        - ![alt text](path/to/image.png "title")

    Args:
        content: Markdown content

    Returns:
        List of image path references (may be relative or absolute)

    Examples:
        >>> extract_image_references("Text ![photo](img.png) more")
        ['img.png']
    """
    # Regex pattern for markdown images: ![alt](path) or ![alt](path "title")
    pattern = r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)'

    matches = re.findall(pattern, content)

    # Extract just the path component (second group)
    image_refs = [match[1] for match in matches]

    if image_refs:
        logger.debug(f"Extracted {len(image_refs)} image references from markdown")

    return image_refs


def resolve_all_image_paths(
    content: str,
    markdown_path: Path,
    folder_path: Path,
) -> tuple[str, list[Path]]:
    """
    Resolve all image paths in markdown content to absolute paths.

    Updates markdown content with absolute paths and returns list of resolved paths.

    Args:
        content: Markdown content with relative image paths
        markdown_path: Absolute path to markdown file
        folder_path: Absolute path to datasheet folder

    Returns:
        Tuple of (updated_content, resolved_image_paths)
            - updated_content: Markdown with absolute image paths
            - resolved_image_paths: List of successfully resolved absolute paths

    Examples:
        >>> content = "![pin](images/pin.png)"
        >>> new_content, paths = resolve_all_image_paths(
        ...     content,
        ...     Path("D:/ds/TL072/TL072.md"),
        ...     Path("D:/ds/TL072")
        ... )
        >>> # new_content: "![pin](D:/ds/TL072/images/pin.png)"
        >>> # paths: [WindowsPath('D:/ds/TL072/images/pin.png')]
    """
    # Extract image references
    image_refs = extract_image_references(content)

    if not image_refs:
        logger.debug("No image references found in markdown")
        return content, []

    resolved_paths = []
    updated_content = content

    # Resolve each image reference
    for image_ref in image_refs:
        resolved_path = resolve_image_path(image_ref, markdown_path, folder_path)

        if resolved_path:
            resolved_paths.append(resolved_path)

            # Replace relative path with absolute path in content
            # Use regex to ensure we only replace within image syntax
            pattern = rf"(!\[[^\]]*\]\(){re.escape(image_ref)}(\))"
            replacement = rf"\1{resolved_path}\2"
            updated_content = re.sub(pattern, replacement, updated_content)

            logger.debug(f"Replaced '{image_ref}' with '{resolved_path}'")
        else:
            logger.warning(
                f"Could not resolve image path '{image_ref}' - "
                f"keeping original reference"
            )

    logger.info(
        f"Resolved {len(resolved_paths)}/{len(image_refs)} image paths successfully"
    )

    return updated_content, resolved_paths


def validate_markdown_structure(content: str) -> dict[str, bool]:
    """
    Validate markdown structure and report issues.

    Checks for:
        - Presence of headers
        - Presence of tables
        - Presence of code blocks
        - Malformed tables (inconsistent column counts)

    Args:
        content: Markdown content

    Returns:
        Dictionary with validation results

    Examples:
        >>> validate_markdown_structure("# Title\\n| A | B |\\n|---|---|\\n| 1 | 2 |")
        {'has_headers': True, 'has_tables': True, 'has_code_blocks': False, 'has_malformed_tables': False}
    """
    validation = {
        "has_headers": bool(re.search(r"^#+\s+", content, re.MULTILINE)),
        "has_tables": bool(re.search(r"^\|.*\|$", content, re.MULTILINE)),
        "has_code_blocks": bool(re.search(r"```", content)),
        "has_malformed_tables": False,
    }

    # Check for malformed tables (basic check)
    if validation["has_tables"]:
        lines = content.split("\n")
        table_lines = [
            line for line in lines if "|" in line and line.strip().startswith("|")
        ]

        if table_lines:
            # Check if table rows have consistent pipe counts
            pipe_counts = [line.count("|") for line in table_lines]
            if len(set(pipe_counts)) > 2:  # Allow for header separator row variation
                validation["has_malformed_tables"] = True
                logger.warning("Detected potentially malformed tables in markdown")

    return validation
