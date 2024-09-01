from jit_utils.models.findings.entities import Finding

from tests.fixtures import sync_specs_on_finding


def assert_finding_full(finding_in_db, expected_finding, **updated_fields):
    expected_finding = expected_finding.copy()
    expected_finding.update(updated_fields)
    assert Finding(**finding_in_db).dict() == Finding(**expected_finding).dict()

    expected_finding = sync_specs_on_finding(expected_finding)
    # Specs are not part of the finding object, so we need to assert them separately
    expected_specs = expected_finding['specs']
    for field, value in updated_fields.items():  # Update the expected specs with the new values
        spec_to_update = next((spec for spec in expected_specs if spec['k'] == field), None)
        if spec_to_update:
            spec_to_update['v'] = value
    assert finding_in_db['specs'] == expected_specs
