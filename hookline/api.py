import secrets
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .config import from_env
from .store import Store


class EndpointInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2048)
    secret: str = Field(min_length=16, max_length=256)


def create_app(settings=None):
    settings = settings or from_env()
    store = Store(settings.database)
    app = FastAPI(title='Hookline', version='0.1.0')
    app.state.store = store

    def authorize(authorization: str = Header(default='')):
        if not secrets.compare_digest(authorization, 'Bearer ' + settings.api_key):
            raise HTTPException(401, 'Invalid access token')

    @app.get('/health')
    def health():
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

    return app
