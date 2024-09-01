from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus


def test_updates_total_assets_for_existing_jit_event_with_moto(jit_event_mock, jit_event_life_cycle_manager):
    # Put an item in the table
    jit_event_life_cycle_manager.put_jit_event(jit_event_mock, JitEventStatus.STARTED)
    # Act
    jit_event_life_cycle_manager.update_jit_event_assets_count(
        jit_event_mock.tenant_id,
        jit_event_mock.jit_event_id,
        100,
    )

    # Assert
    response = jit_event_life_cycle_manager.get_jit_event(jit_event_mock.tenant_id, jit_event_mock.jit_event_id)
    assert response.total_assets == 100
    assert response.remaining_assets == 100
