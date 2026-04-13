import secrets
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .config import from_env
from .store import Store


class EndpointInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2048)
    secret: str = Field(min_length=16, max_length=256)


class EventInput(BaseModel):
    endpoint_id: int = Field(gt=0)
    key: str = Field(min_length=1, max_length=200)
    payload: dict
    max_attempts: int = Field(default=5, ge=1, le=20)


def create_app(settings=None):
    settings = settings or from_env()
    store = Store(settings.database)
    app = FastAPI(title='Hookline', version='0.1.0')
    app.state.store = store

    def authorize(authorization: str = Header(default='')):
        if not secrets.compare_digest(authorization.encode(), ('Bearer ' + settings.api_key).encode()):
            raise HTTPException(401, 'Invalid access token')

    @app.get('/health')
    def health():
        try:
            with store.connection() as db:
                db.execute('SELECT id FROM events LIMIT 1').fetchone()
        except Exception as error:
            raise HTTPException(503, 'Storage is unavailable') from error
        return {'status': 'ok'}

    @app.post('/endpoints', dependencies=[Depends(authorize)], status_code=201)
    def add_endpoint(body: EndpointInput):
        try:
            settings.validate_url(body.url)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        endpoint_id = store.add_endpoint(body.name, body.url, body.secret)
        return {'id': endpoint_id, 'name': body.name, 'url': body.url}

    @app.get('/endpoints', dependencies=[Depends(authorize)])
    def endpoints():
        return store.endpoints()

    @app.post('/events', dependencies=[Depends(authorize)], status_code=202)
    def enqueue(body: EventInput):
        try:
            event, created = store.enqueue(body.endpoint_id, body.key, body.payload,
                                           body.max_attempts)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {'id': event['id'], 'state': event['state'], 'created': created}

    @app.get('/events/{event_id}', dependencies=[Depends(authorize)])
    def event(event_id: str):
        result = store.event(event_id)
        if result is None:
            raise HTTPException(404, 'Event not found')
        return {key: value for key, value in result.items()
                if key not in {'lease_token', 'lease_until'}}

    @app.post('/events/{event_id}/replay', dependencies=[Depends(authorize)])
    def replay(event_id: str):
        try:
            store.replay(event_id)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {'id': event_id, 'state': 'pending'}

    @app.get('/events/{event_id}/attempts', dependencies=[Depends(authorize)])
    def attempts(event_id: str):
        if store.event(event_id) is None:
            raise HTTPException(404, 'Event not found')
        return store.attempts(event_id)

    @app.get('/events', dependencies=[Depends(authorize)])
    def events(state: str = None, limit: int = 50, offset: int = 0):
        try:
            return store.events(state, limit, offset)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.patch('/endpoints/{endpoint_id}', dependencies=[Depends(authorize)])
    def enable(endpoint_id: int, enabled: bool):
        try:
            store.set_enabled(endpoint_id, enabled)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error
        return {'id': endpoint_id, 'enabled': enabled}

    @app.get('/stats', dependencies=[Depends(authorize)])
    def stats():
        return store.stats()

    return app
