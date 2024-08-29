from src.lib.ignore_rules.utils import build_path_for_finding_filename


def test_simple_path():
    assert build_path_for_finding_filename(['/path', 'to', 'file.txt']) == 'path/to/file.txt'


def test_path_with_leading_slash():
    assert build_path_for_finding_filename(['/path/', '/to', '/file.txt']) == 'path/to/file.txt'


def test_path_with_mixed_slash():
    assert build_path_for_finding_filename(['/path', 'to/', 'file.txt']) == 'path/to/file.txt'


def test_path_with_no_slash():
    assert build_path_for_finding_filename(['path', 'to', 'file.txt']) == 'path/to/file.txt'


def test_single_path_part():
    assert build_path_for_finding_filename(['file.txt']) == 'file.txt'


def test_path_with_special_characters():
    assert build_path_for_finding_filename(['/path/', '/to-file*', 'file.txt']) == 'path/to-file*/file.txt'
