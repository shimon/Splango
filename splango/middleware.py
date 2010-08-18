from splango import RequestExperimentManager

class ExperimentsMiddleware:

    def process_request(self, request):
        request.experiments = RequestExperimentManager(request)
        return None

    def process_response(self, request, response):
        if getattr(request, "experiments", None):
            request.experiments.finish(response)
        return response
