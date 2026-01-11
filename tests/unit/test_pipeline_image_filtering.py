"""
Unit tests for pipeline image filtering functionality.

Tests the _filter_chunk_image_paths function to ensure only images
referenced in a chunk are added to that chunk's image_paths.
"""

from pathlib import Path

from src.ingestion.pipeline import _filter_chunk_image_paths


def test_filter_chunk_image_paths_no_images():
    """Test chunk with no image references returns empty list."""
    chunk_text = "This is a chunk with no images."
    all_images = [Path("D:/test/image1.png"), Path("D:/test/image2.png")]

    result = _filter_chunk_image_paths(chunk_text, all_images)

    assert result == []


def test_filter_chunk_image_paths_single_image():
    """Test chunk with single image reference."""
    chunk_text = "Here is an image: ![alt](image1.png)"
    all_images = [Path("D:/test/image1.png"), Path("D:/test/image2.png")]

    result = _filter_chunk_image_paths(chunk_text, all_images)

    assert len(result) == 1
    assert "D:\\test\\image1.png" in result[0] or "D:/test/image1.png" in result[0]


def test_filter_chunk_image_paths_multiple_images():
    """Test chunk with multiple image references."""
    chunk_text = """
    First image: ![alt1](image1.png)
    Second image: ![alt2](image2.png)
    """
    all_images = [
        Path("D:/test/image1.png"),
        Path("D:/test/image2.png"),
        Path("D:/test/image3.png"),
    ]

    result = _filter_chunk_image_paths(chunk_text, all_images)

    assert len(result) == 2
    # Check that both images are in result
    result_str = " ".join(result)
    assert "image1.png" in result_str
    assert "image2.png" in result_str
    assert "image3.png" not in result_str


def test_filter_chunk_image_paths_duplicate_references():
    """Test chunk with duplicate image references."""
    chunk_text = """
    First: ![alt1](image1.png)
    Again: ![alt2](image1.png)
    """
    all_images = [Path("D:/test/image1.png")]

    result = _filter_chunk_image_paths(chunk_text, all_images)

    # Should only include image once
    assert len(result) == 1
    assert "image1.png" in result[0]


def test_filter_chunk_image_paths_unresolved_reference():
    """Test chunk referencing image not in resolved list."""
    chunk_text = "Image: ![alt](missing.png)"
    all_images = [Path("D:/test/image1.png")]

    result = _filter_chunk_image_paths(chunk_text, all_images)

    # Should not include unresolved image
    assert result == []


def test_filter_chunk_image_paths_absolute_path():
    """Test chunk with absolute path reference."""
    abs_path = "D:/test/subdir/image1.png"
    chunk_text = f"Image: ![alt]({abs_path})"
    all_images = [Path(abs_path)]

    result = _filter_chunk_image_paths(chunk_text, all_images)

    assert len(result) == 1
    assert abs_path in result[0] or abs_path.replace("/", "\\") in result[0]


def test_filter_chunk_image_paths_mixed_references():
    """Test chunk with mix of relative and absolute references."""
    abs_path = "D:/test/image2.png"
    chunk_text = f"""
    Relative: ![alt1](image1.png)
    Absolute: ![alt2]({abs_path})
    """
    all_images = [
        Path("D:/test/image1.png"),
        Path(abs_path),
        Path("D:/test/image3.png"),
    ]

    result = _filter_chunk_image_paths(chunk_text, all_images)

    assert len(result) == 2
    result_str = " ".join(result)
    assert "image1.png" in result_str
    assert "image2.png" in result_str
    assert "image3.png" not in result_str
