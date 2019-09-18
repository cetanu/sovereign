import schedule
from pydantic import BaseModel
from typing import List
from fastapi import Body, BackgroundTasks
from fastapi.routing import APIRouter
from starlette.responses import JSONResponse
from sovereign import discovery, statsd, config
# from sovereign.schemas import DiscoveryRequest
from sovereign.utils.auth import authenticate

router = APIRouter()


class Locality(BaseModel):
    region: str = None
    zone: str = None
    sub_zone: str = None


class Node(BaseModel):
    id: str = '-'
    cluster: str
    build_version: str
    metadata: dict = None
    locality: Locality = Locality()


class DiscoveryRequest(BaseModel):
    node: Node
    version_info: str = '0'
    resource_names: List[str] = list()

    @property
    def envoy_version(self):
        try:
            build_version = self.node.build_version
            revision, version, *other_metadata = build_version.split('/')
        except (AttributeError, ValueError):
            # TODO: log/metric this?
            return 'default'
        return version


@router.post('/v2/discovery:{xds_type}')
async def discovery_response(
        xds_type: str,
        background_tasks: BackgroundTasks,
        r: DiscoveryRequest = Body(None),
):
    background_tasks.add_task(schedule.run_pending)

    authenticate(r)
    response = await discovery.response(r, xds_type)

    if response['version_info'] == r.version_info:
        ret = 'No changes'
        code = config.no_changes_response_code
    elif not response['resources']:
        ret = 'No resources found'
        code = 404
    elif response['version_info'] != r.version_info:
        ret = response
        code = 200
    else:
        ret = 'Unknown Error'
        code = 500

    try:
        client_ip = r.node.metadata.get('ipv4')
    except KeyError:
        client_ip = '-'

    metrics_tags = [
        f"client_ip:{client_ip}",
        f"client_version:{r.envoy_version}",
        f"response_code:{code}",
        f"xds_type:{xds_type}"
    ]
    metrics_tags += [f"resource:{resource}" for resource in r.resource_names]
    statsd.increment('discovery.rq_total', tags=metrics_tags)
    return JSONResponse(content=ret, status_code=code)
