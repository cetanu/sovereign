from sovereign.v2.data.repositories import ContextRepository, DiscoveryEntryRepository
from sovereign.v2.types import RenderDiscoveryJob


def render_discovery_response(
    context_repository: ContextRepository,
    discovery_job_repository: DiscoveryEntryRepository,
    job: RenderDiscoveryJob,
):
    pass
    # discovery_job = discovery_job_repository.get(job.request_hash)
    # version = discovery_job.request.envoy_version
    # xds_template: XdsTemplate = XDS_TEMPLATES.get(version).get(
    #     discovery_job.request.template
    # )
    # required_context_names = xds_template.depends_on
    # context: dict[str, Any] = {"request": discovery_job.request}
    # for context_name in required_context_names:
    #     context[context_name] = context_repository.get(context_name)
    # # todo: crypto
    # # todo: hide ui
    # render_job: RenderJob = RenderJob(
    #     id=job.request_hash, request=job.request, context=context
    # )
