from django.template import RequestContext
from django.views.decorators.cache import never_cache
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render_to_response, get_object_or_404

from django.http import HttpResponse

from splango.models import *

@never_cache
def confirm_human(request):
    request.experiments.confirm_human()
    return HttpResponse(status=204)


@staff_member_required
def experiments_overview(request):
    exps = Experiment.objects.all()

    repts = ExperimentReport.objects.all()
    
    repts_by_id = dict()

    for r in repts:
        repts_by_id.setdefault(r.experiment_id, []).append(r)

    for exp in exps:
        exp.reports = repts_by_id.get(exp.name, [])

    return render_to_response("splango/experiments_overview.html",
                              {"title":"Experiments",
                               "exps": exps },
                              RequestContext(request))

@staff_member_required
def experiment_detail(request, expname):
    exp = get_object_or_404(Experiment, name=expname)

    repts = ExperimentReport.objects.filter(experiment=exp)

    return render_to_response("splango/experiment_detail.html",
                              {"title":exp.name,
                               "exp": exp,
                               "repts": repts
                               },
                              RequestContext(request))

@staff_member_required
def experiment_report(request, expname, report_id):

    rept = get_object_or_404(ExperimentReport, id=report_id,
                             experiment__name=expname)

    report_rows = rept.generate()

    return render_to_response("splango/experiment_report.html",
                              { "title": rept.title,
                                "exp": rept.experiment,
                                "rept": rept,
                                "report_rows": report_rows,
                                },
                              RequestContext(request))


@staff_member_required
def experiment_log(request, expname, variant, goal):
    exp = get_object_or_404(Experiment, name=expname)
    goal = get_object_or_404(Goal, name=goal)

    enrollments = Enrollment.objects.filter(experiment=exp, 
                                            variant=variant, 
                                            subject__goals=goal).select_related("subject")[:1000]
    # 1000 limit is just there to keep this page sane

    goalrecords = GoalRecord.objects.filter(
        goal=goal,
        subject__in=[ e.subject for e in enrollments ]).select_related("goal","subject")

    title = "Experiment Log: variant %s, goal %s" % (variant, goal)

    activities = list(enrollments)+list(goalrecords)

    activities.sort(key=lambda x: x.created)

    return render_to_response("splango/experiment_log.html",
                              { "exp": exp,
                                "activities": activities,
                                "title": title },
                              RequestContext(request))


