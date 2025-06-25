import pytest
from app import app,mongo
import json

@pytest.fixture(scope='session',autouse=True)
def before_all_tests():
    mongo.db.users.delete_many({}) # type: ignore
@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client                
signUp_cases = [
    ({'uname': 'test1', 'password': '123'}, 201),  # Valid
    ({'uname': 'test1', 'password': '123'}, 409),  # Duplicate
    ({'uname': '', 'password': '123'}, 400),       # Missing uname
    ({'password': '123'}, 400),                    # Missing uname field
    ({'uname': 'test5'}, 400),                     # Missing password field
    ({}, 400),                                     # Empty object
]
@pytest.mark.parametrize('payload,expected',signUp_cases)
def test_signup(client,payload,expected):
    response = client.post('/signUp',data = json.dumps(payload),content_type='application/json') # type: ignore
    assert response.status_code == expected # type: ignore

logIn_cases = [
    ({'uname': 'test1', 'password': '123'}, 200),  # valid    
    ({'uname': 'test1', 'password': '12'}, 400),   # Wrong Password
    ({'uname': '', 'password': '123'}, 400),       # Missing uname
    ({'password': '123'}, 400),                    # Missing uname field
    ({'uname': 'test5'}, 400),                     # Missing password field
    ({}, 400),                                     # Empty object
]
@pytest.mark.parametrize('payload,expected',logIn_cases)
def test_login(client,payload,expected):
    response = client.post('/login',data = json.dumps(payload),content_type='application/json') # type: ignore
    assert response.status_code == expected     # type: ignore
    

def create_user_and_login(client, uname='user1', password='pass'):
    client.post('/signUp', data=json.dumps({'uname': uname, 'password': password}), content_type='application/json')
    resp = client.post('/login', data=json.dumps({'uname': uname, 'password': password}), content_type='application/json')
    token = resp.get_json().get('token')
    return token

@pytest.fixture(autouse=True)
def clear_polls():
    mongo.db.poll.delete_many({}) # type: ignore

def test_get_all_poll(client):
    mongo.db.poll.insert_one({'_id': 100, 'title': 'Poll', 'option': ['A'], 'created_by': 'user1', 'voting': []}) # type: ignore
    resp = client.get('/poll')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert any(p['title'] == 'Poll' for p in data)

@pytest.mark.parametrize("poll_data, expected_status", [
    ({'title': 'Poll', 'option': ['A'], 'created_by': 'user1', 'voting': []}, 200),
])
def test_vote_success_and_fail(client, poll_data, expected_status):
    poll_id = 200
    poll_data = poll_data.copy()
    poll_data['_id'] = poll_id
    mongo.db.poll.insert_one(poll_data) # type: ignore
    # Success
    resp = client.post(f'/vote/{poll_id}', data=json.dumps({'option': 'A'}), content_type='application/json')
    assert resp.status_code == expected_status
    # Missing option
    resp = client.post(f'/vote/{poll_id}', data=json.dumps({}), content_type='application/json')
    assert resp.status_code == 400
    # Poll not found
    resp = client.post('/vote/9999', data=json.dumps({'option': 'A'}), content_type='application/json')
    assert resp.status_code == 404

def test_get_my_poll(client):
    token = create_user_and_login(client, 'mypolluser', 'pass')
    mongo.db.poll.insert_one({'_id': 300, 'title': 'MyPoll', 'option': ['A'], 'created_by': 'mypolluser', 'voting': []}) # type: ignore
    headers = {'Authorization': f'Bearer {token}'}
    resp = client.get('/mypoll', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert any(p['title'] == 'MyPoll' for p in data)

def test_get_my_poll_unauth(client):
    resp = client.get('/mypoll')
    assert resp.status_code == 401

def test_delete_my_poll(client):
    token = create_user_and_login(client, 'deluser', 'pass')
    poll_id = 400
    mongo.db.poll.insert_one({'_id': poll_id, 'title': 'DelPoll', 'option': ['A'], 'created_by': 'deluser', 'voting': []}) # type: ignore
    headers = {'Authorization': f'Bearer {token}'}
    resp = client.delete(f'/poll/{poll_id}', headers=headers)
    assert resp.status_code == 200
    # Try deleting again, should return 400 (not found)
    resp = client.delete(f'/poll/{poll_id}', headers=headers)
    assert resp.status_code in (200, 400)

def test_update_option(client):
    token = create_user_and_login(client, 'updateuser', 'pass')
    poll_id = 500
    mongo.db.poll.insert_one({'_id': poll_id, 'title': 'UpdPoll', 'option': ['A'], 'created_by': 'updateuser', 'voting': []}) # type: ignore
    headers = {'Authorization': f'Bearer {token}'}
    resp = client.put(f'/poll/{poll_id}', data=json.dumps({'new_option': 'B'}), content_type='application/json', headers=headers)
    assert resp.status_code in (200, 400)
