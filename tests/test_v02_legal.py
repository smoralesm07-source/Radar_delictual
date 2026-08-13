from radar_delictual.legal import classify_mp_code, legal_summary

def test_laundering_codes_are_explicit():
    assert classify_mp_code(12133)['class']=='laundering_offense'
    assert classify_mp_code(12174)['class']=='laundering_offense'

def test_predicate_and_org_signal_are_separate():
    assert classify_mp_code(7007)['class']=='predicate_direct'
    assert classify_mp_code(12051)['class']=='predicate_direct'
    assert classify_mp_code(806)['class']=='organized_crime_signal'
    assert classify_mp_code(12053)['class']=='predicate_candidate'

def test_nonvigent_and_unknown_not_promoted():
    assert classify_mp_code(7035)['class']=='historical_nonvigent'
    assert classify_mp_code(7098)['class']=='historical_nonvigent'
    assert classify_mp_code(999999)['class']=='unmapped'

def test_summary_version(): assert legal_summary()['version']=='0.2.0'

def test_verified_expanded_predicates_and_org_signals():
    assert classify_mp_code(202)['class']=='predicate_direct'
    assert classify_mp_code(12135)['class']=='predicate_direct'
    assert classify_mp_code(551)['class']=='predicate_direct'
    assert classify_mp_code(542)['class']=='organized_crime_signal'
