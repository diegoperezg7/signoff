from fastapi.testclient import TestClient
import base64
from app.main import app

client = TestClient(app)


def test_health_and_demo_dashboard():
    assert client.get('/health').json()['status'] == 'ok'
    data = client.get('/api/v1/dashboard').json()
    assert data['project']['name'] == 'Customer Operations Portal v1'
    assert data['requirements'] == 12


def test_requirements_and_mock_run():
    requirements = client.get('/api/v1/projects/project_demo/requirements').json()
    assert len(requirements) == 12
    result = client.post('/api/v1/projects/project_demo/runs', json={'requirement_ids': [requirements[0]['id']]}).json()
    assert result['status'] == 'completed'
    assert result['evidence'][0]['state'] == 'demonstrated'


def test_review_token():
    assert client.post('/api/v1/review/nope', json={'decision': 'accepted'}).status_code == 404
    response = client.post('/api/v1/review/demo-review-token', json={'decision': 'accepted', 'comment': 'Looks good'})
    assert response.json()['status'] == 'recorded'


def test_scope_readiness_graph_and_acceptance():
    versions = client.get('/api/v1/projects/project_demo/scope/versions').json()
    assert versions[0]['version'] == 'v1'
    readiness = client.get('/api/v1/projects/project_demo/readiness').json()
    assert readiness['total_requirements'] == 12
    graph = client.get('/api/v1/projects/project_demo/graph').json()
    assert graph['nodes']
    requirements = client.get('/api/v1/projects/project_demo/requirements').json()
    decision = client.post(f"/api/v1/projects/project_demo/acceptance/{requirements[8]['id']}", json={'decision': 'accepted'}).json()
    assert decision['decision'] == 'accepted'


def test_file_inspector_and_bug_change_classification():
    csv = base64.b64encode(b"id,status\n1,open\n2,closed\n").decode()
    result = client.post('/api/v1/projects/project_demo/file-inspections', json={'filename': 'orders.csv', 'content_base64': csv, 'expected_columns': ['id', 'status'], 'expected_row_count': 2}).json()
    assert result['valid'] is True
    assert result['assessment'] == 'demonstrated'
    report = client.post('/api/v1/projects/project_demo/bug-change-assessment', json={'report': 'The filtered export returns all rows', 'requirement_ids': []}).json()
    assert report['classification'] == 'likely_defect'


def test_two_projects_use_one_dashboard_contract():
    projects = client.get('/api/v1/projects').json()['items']
    assert {item['id'] for item in projects} == {'project_acme', 'project_demo'}
    acme = client.get('/api/v1/projects/project_acme/releases/release_2_3/dashboard').json()
    customer = client.get('/api/v1/projects/project_demo/releases/release_1_0/dashboard').json()
    assert acme['project']['name'] == 'Acme Inc.'
    assert acme['project']['id'] != customer['project']['id']
    assert acme['metrics']['requirements']['value'] == 86
    assert customer['metrics']['requirements']['value'] == 12


def test_ai_proposal_requires_approval_and_is_traced():
    response = client.post('/api/v1/projects/project_demo/ai/tasks', json={'task': 'generate_acceptance_criteria', 'context': {'title': 'CSV export'}})
    assert response.status_code == 200
    proposal = response.json()
    assert proposal['status'] == 'draft'
    assert proposal['provider'] == 'MockLLMProvider'
    approved = client.post(f"/api/v1/ai/proposals/{proposal['id']}/approve")
    assert approved.json()['status'] == 'approved'
    assert client.get('/api/v1/projects/project_demo/ai/runs').json()


def test_functional_endpoints_follow_the_active_project():
    acme_requirements = client.get('/api/v1/projects/project_acme/requirements').json()
    customer_requirements = client.get('/api/v1/projects/project_demo/requirements').json()
    assert len(acme_requirements) == 86
    assert len(customer_requirements) == 12
    assert client.get('/api/v1/projects/project_acme/changes').json()
    assert client.get('/api/v1/projects/project_acme/scope/versions').json()[0]['version'] == 'BR-1.4'
    assert client.get('/api/v1/projects/project_acme/readiness').json()['total_requirements'] == 86
    assert client.get('/api/v1/projects/project_acme/graph').json()['nodes']
    assert client.get('/api/v1/projects/project_acme/delivery-pack').json()['project']['id'] == 'project_acme'
    assert client.get('/api/v1/projects/project_demo/delivery-pack').json()['project']['id'] == 'project_demo'


def test_human_requirement_ids_can_start_shared_verification():
    response = client.post('/api/v1/projects/project_acme/runs', json={'requirement_ids': ['REQ-041']})
    assert response.status_code == 200
    assert response.json()['evidence'][0]['requirement_id'] == acme_requirement_id('REQ-041')


def test_delivery_prepare_and_client_acceptance_are_persisted_in_mock_flow():
    prepared = client.post('/api/v1/projects/project_demo/prepare-delivery')
    assert prepared.status_code == 200
    assert prepared.json()['checks']
    accepted = client.post('/api/v1/review/demo-review-token', json={'decision': 'accepted', 'comment': 'Approved for handoff'})
    assert accepted.status_code == 200
    assert accepted.json()['review']['project_id'] == 'project_demo'
    assert client.get('/api/v1/projects/project_demo/releases/release_1_0/dashboard').json()['project']['status'] == 'accepted'


def test_evidence_links_expire_and_are_signed():
    evidence = client.get('/api/v1/projects/project_demo/evidence').json()[0]
    signed = client.get(f"/api/v1/projects/project_demo/evidence/{evidence['artifact']}/signed-url").json()['url']
    assert 'signature=' in signed
    assert 'expires=' in signed


def acme_requirement_id(human_id: str) -> str:
    requirements = client.get('/api/v1/projects/project_acme/requirements').json()
    return next(item['id'] for item in requirements if item['human_id'] == human_id)
