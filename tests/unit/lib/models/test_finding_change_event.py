import json
from typing import Optional, Union

import pytest
from jit_utils.models.findings.entities import Resolution, Finding, UiResolution

from src.lib.models.finding_change_event import FindingChangeEvent
from tests.fixtures import build_finding_dict


@pytest.mark.parametrize("prev_resolution, new_resolution",
                         [(None, Resolution.OPEN),
                          (Resolution.FIXED, Resolution.OPEN),
                          (Resolution.INACTIVE, None)])
def test_create_finding_change_event_happy_flow(prev_resolution: Optional[Union[UiResolution, Resolution]],
                                                new_resolution: Optional[Union[UiResolution, Resolution]]):
    assert FindingChangeEvent(finding=Finding(**build_finding_dict()),
                              prev_resolution=prev_resolution,
                              new_resolution=new_resolution)


@pytest.mark.parametrize("finding_change_event, contained_in_event",
                         [
                             (FindingChangeEvent(finding=Finding(**build_finding_dict()), prev_resolution=None,
                                                 new_resolution=Resolution.OPEN),
                              {"priority_factors": []}),
                             (FindingChangeEvent(finding=Finding(
                                 **build_finding_dict(priority_factors=["Production", "Non-Production"])),
                                                 prev_resolution=None, new_resolution=Resolution.OPEN),
                              {"priority_factors": ["Production", "Non-Production"]}),
                             (FindingChangeEvent(finding=Finding(**build_finding_dict()), prev_resolution=None,
                                                 new_resolution=Resolution.OPEN),
                              {"priority_score": 0}),
                             (FindingChangeEvent(finding=Finding(**build_finding_dict(priority_score=123)),
                                                 prev_resolution=None, new_resolution=Resolution.OPEN),
                              {"priority_score": 123}),
                             (FindingChangeEvent(finding=Finding(**build_finding_dict()), prev_resolution=None,
                                                 new_resolution=Resolution.OPEN),
                              {"asset_priority_score": 0}),
                             (FindingChangeEvent(finding=Finding(**build_finding_dict(asset_priority_score=123)),
                                                 prev_resolution=None, new_resolution=Resolution.OPEN),
                              {"asset_priority_score": 123}),
                         ])
def test_finding_change_event__serialize_contains(finding_change_event: FindingChangeEvent,
                                                  contained_in_event: dict):
    serialized = finding_change_event.serialize()
    serialized = json.loads(serialized)
    for key, value in contained_in_event.items():
        assert serialized[key] == value
