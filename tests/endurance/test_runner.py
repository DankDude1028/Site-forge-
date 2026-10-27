from siteforge.endurance import Simulation, THRESHOLDS


def test_fixture_pipeline_recovers_persisted_tasks_and_fences_old_worker(tmp_path):
    simulation=Simulation(tmp_path)
    result=simulation.cycle(0)
    assert len(result['task_ids'])==3
    assert set(result['injected'])==set(result['recovered'])
    assert 'lease_expiration' in result['recovered']
    simulation.restart()
    assert simulation.cycle(0)['task_ids'] == result['task_ids']
    simulation.db.dispose()


def test_thresholds_require_actual_72_hours_and_hundreds_of_tasks():
    assert THRESHOLDS['minimum_active_seconds']==259200
    assert THRESHOLDS['minimum_completed_tasks']>=900
    assert THRESHOLDS['unauthorized_effects']==0
