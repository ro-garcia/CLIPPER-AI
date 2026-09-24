import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from pydantic import ValidationError
from app.main import app
from app.database import Session
from app.detection.models import DetectionRule, RuleGroup, DetectionProfile, DetectionState
from app.detection.repository import RulesRepository, rules_repository
from app.detection.schemas import RuleInput
from app.detection.extractor import evaluate_text
from app.detection.runtime import DetectionSignals

@pytest.fixture
def client():
    with TestClient(app) as client:
        with Session.begin() as db:
            for model in (DetectionRule, RuleGroup, DetectionProfile):
                db.execute(delete(model))
            db.get(DetectionState, 1).active_profile_id = None
        rules_repository.load()
        yield client

def rule(client, **values):
    payload = {'name':'Test signal', 'pattern':'Example', 'weight':.2, **values}
    response = client.post('/moment-rules', json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def preview(client, text='example', language='*'):
    response = client.post('/moment-rules/preview', json={'text':text, 'language':language})
    assert response.status_code == 200, response.text
    return response.json()

def test_crud_cache_and_no_automatic_moment(client):
    created = rule(client)
    assert preview(client, 'example example example')['detection_confidence'] == .2
    payload = {key:created[key] for key in RuleInput.model_fields}
    response = client.put('/moment-rules/'+created['id'], json={**payload, 'pattern':'Changed', 'weight':.9})
    assert response.status_code == 200
    assert response.json()['updated_at'] != created['updated_at']
    assert preview(client)['matches'] == []
    result = preview(client, 'changed')
    assert result['detection_confidence'] == .9
    assert not result['creates_clip'] and not result['creates_moment']
    client.post(f"/moment-rules/{created['id']}/disable")
    assert preview(client, 'changed')['matches'] == []
    client.post(f"/moment-rules/{created['id']}/enable")
    assert len(preview(client, 'changed')['matches']) == 1
    client.delete('/moment-rules/'+created['id'])
    rules_repository.load()
    assert preview(client, 'changed')['matches'] == []  # No seed resurrection.
    assert client.delete('/moment-rules/'+created['id']).status_code == 404

@pytest.mark.parametrize('mode,text,expected',[
    ('EXACT','example',True), ('EXACT','an example',False),
    ('CONTAINS','an example here',True), ('CONTAINS','elsewhere',False),
    ('STARTS_WITH','example here',True), ('STARTS_WITH','an example',False),
    ('ENDS_WITH','an example',True), ('ENDS_WITH','example here',False),
])
def test_match_modes(client, mode, text, expected):
    rule(client, match_type=mode)
    assert bool(preview(client,text)['matches']) is expected

def test_case_unicode_language_and_negative_weights(client):
    rule(client, pattern='Café', language='fr', case_sensitive=True, weight=.3)
    assert preview(client,'Cafe\u0301','fr-CA')['detection_confidence'] == .3
    assert preview(client,'café','fr')['matches'] == []
    assert preview(client,'Café','es')['matches'] == []
    assert preview(client,'Café','*')['matches'] == []
    rule(client, pattern='Café', language='*', weight=-.5)
    assert preview(client,'Café','fr')['detection_confidence'] == 0
    assert preview(client,'Café','fr')['linguistic_weight'] == -.2

def test_profiles_groups_and_restart_persistence(client):
    group = client.post('/moment-rules/groups', json={'name':'My group'}).json()
    grouped = rule(client, group_id=group['id'])
    independent = rule(client, name='Other signal')
    profile = client.post('/moment-profiles', json={'name':'My profile','group_ids':[group['id']]}).json()
    client.post('/moment-profiles/active', json={'profile_id':profile['id']})
    assert [m['rule_id'] for m in preview(client)['matches']] == [grouped['id']]
    other_repository = RulesRepository()
    other_repository.load()
    assert other_repository.cache.snapshot.profile_id == profile['id']
    assert client.delete('/moment-profiles/'+profile['id']).status_code == 409
    client.put('/moment-rules/groups/'+group['id'], json={'name':'My group','enabled':False})
    assert preview(client)['matches'] == []
    client.put('/moment-profiles/'+profile['id'], json={'name':'Updated profile','rule_ids':[independent['id']]})
    assert [m['rule_id'] for m in preview(client)['matches']] == [independent['id']]
    client.post('/moment-profiles/active', json={'profile_id':None})
    assert len(preview(client)['matches']) == 1  # Disabled group still excluded.
    client.delete('/moment-rules/groups/'+group['id'])
    saved = next(row for row in client.get('/moment-rules').json() if row['id']==grouped['id'])
    assert saved['group_id'] is None and saved['enabled'] is False
    client.delete('/moment-rules/'+independent['id'])
    assert client.get('/moment-profiles').json()[0]['rule_ids'] == []

def test_json_roundtrip_and_atomic_validation(client):
    group = client.post('/moment-rules/groups',json={'name':'Group'}).json()
    created = rule(client,group_id=group['id'])
    profile = client.post('/moment-profiles',json={'name':'Profile','group_ids':[group['id']],'rule_ids':[created['id']]}).json()
    client.post('/moment-profiles/active',json={'profile_id':profile['id']})
    bundle = client.get('/moment-rules/export').json()
    result = client.post('/moment-rules/import',json=bundle)
    assert result.status_code == 200, result.text
    config = client.get('/moment-rules/configuration').json()
    assert len(config['rules']) == 2 and len(config['groups']) == 2
    assert config['active_profile_id'] == profile['id']
    imported = next(row for row in config['rules'] if row['id'] != created['id'])
    assert imported['group_id'] != created['group_id']
    imported_profile = next(row for row in config['profiles'] if row['id'] != profile['id'])
    assert imported_profile['rule_ids'] == [imported['id']]
    bundle['rules'][0]['group_id'] = 'missing'
    assert client.post('/moment-rules/import',json=bundle).status_code == 422
    assert len(client.get('/moment-rules').json()) == 2
    bundle['schema_version'] = 99
    assert client.post('/moment-rules/import',json=bundle).status_code == 422

@pytest.mark.parametrize('changes',[{'weight':1.01},{'pattern':'   '},{'match_type':'REGEX'},
                                    {'language':'not a language'}, {'unknown_field':'value'}])
def test_invalid_configuration_rejected(client,changes):
    assert client.post('/moment-rules',json={'name':'Signal','pattern':'test',**changes}).status_code == 422
    assert client.get('/moment-rules').json() == []

def test_regex_characters_are_literal_and_nonfinite_rejected(client):
    rule(client,pattern='(a+)+$')
    assert preview(client,'aaaaaaaaaaaaaaaaaa')['matches'] == []
    assert len(preview(client,'(a+)+$')['matches']) == 1
    with pytest.raises(ValidationError):
        RuleInput(name='Test',pattern='a',weight=float('nan'))

def test_extractor_never_queries_database(client,monkeypatch):
    rule(client)
    import app.detection.repository as module
    def unexpected_database():
        raise AssertionError('Extractor accessed SQLite')
    monkeypatch.setattr(module,'Session',unexpected_database)
    assert evaluate_text('example','*',rules_repository.cache.snapshot)['detection_confidence'] == .2

def test_live_window_reacts_to_cache_changes_without_new_audio(client):
    rule(client)
    runtime = DetectionSignals()
    runtime.reset('current')
    runtime.observe('old',[{'start':0,'end':5,'text':'example'}],'en')
    assert not runtime.status()['has_audio']
    runtime.observe('current',[{'start':0,'end':5,'text':'example'}],'en')
    assert runtime.status()['detection_confidence'] == .2
    second = rule(client,weight=.4)
    assert runtime.status()['detection_confidence'] == .6
    client.post(f"/moment-rules/{second['id']}/disable")
    assert runtime.status()['detection_confidence'] == .2

def test_cors_put_and_delete(client):
    for method in ('PUT','DELETE'):
        response = client.options('/moment-rules/id',headers={
            'Origin':'http://127.0.0.1:5173','Access-Control-Request-Method':method})
        assert response.status_code == 200
