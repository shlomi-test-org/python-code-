from abc import ABC
from typing import Type

import jit_utils
from jit_utils.event_models import JitEvent, RegisterScheduledTasksJitEvent, UnregisterScheduledTasksJitEvent
from test_utils.reflection import collect_child_classes, find_factory_by_model

import tests

all_jit_event_types = collect_child_classes(package=jit_utils, cls=JitEvent)


def is_abstract(cls: Type) -> bool:
    return ABC in cls.__bases__


supported_jit_event_types = [jit_event_type for jit_event_type in all_jit_event_types
                             if not is_abstract(jit_event_type)
                             # TODO remove after sc-18177
                             and jit_event_type not in [
                                 RegisterScheduledTasksJitEvent,
                                 UnregisterScheduledTasksJitEvent]]


def generate_jit_event(jit_event_type: Type[JitEvent]) -> JitEvent:
    """
    Generate a JitEvent instance of the given type or skip the test if the factory is not found.
    Args:
        jit_event_type: type of the JitEvent to generate

    Returns:
        JitEvent instance of the given type
    """
    factory = find_factory_by_model(tests, jit_event_type)

    if factory is None:
        raise Exception(f"Factory not found for {jit_event_type}")

    return factory.build()


# Must be sorted to make the test deterministic
supported_jit_events = sorted([generate_jit_event(jit_event_type) for jit_event_type in supported_jit_event_types],
                              key=lambda jit_event: type(jit_event).__name__)
