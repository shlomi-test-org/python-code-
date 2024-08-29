import pytest

from src.lib.models.finding_model import FindingsForScanScope, ScanScopeType


@pytest.mark.parametrize(
    'scan_scope, scan_scope_to_check, expected_result',
    [
        [dict(branch='master'), dict(branch='master'), True],
        [dict(branch='master', filepath='a.py'), dict(branch='master', filepath='a.py'), True],
        [dict(branch='master'), dict(branch='master', filepath='a.py'), True],
        [dict(branch='master'), dict(branch='master', filepath='a.py', line_range='1-2'), True],
        [dict(branch='master'), dict(branch='develop'), False],
        [dict(branch='master'), dict(branch='develop', filepath='a.py'), False],
        [dict(branch='master'), dict(filepath='a.py'), False],
    ],
)
def test_is_scope_contained(scan_scope: ScanScopeType, scan_scope_to_check: ScanScopeType, expected_result: bool):
    group = FindingsForScanScope(findings=[], scan_scope=scan_scope)
    assert group.is_scope_contained(scan_scope_to_check) is expected_result
