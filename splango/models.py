from django.db import models
from django.contrib.auth.models import User

import logging

#from django.db.models import Avg, Max, Min, Count

import random

_NAME_LENGTH=30

class Goal(models.Model):
    name = models.CharField(max_length=_NAME_LENGTH, primary_key=True)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name


class Subject(models.Model):
    """An experimental subject, possibly also a registered user (at creation
    or later on."""

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    registered_as = models.ForeignKey(User, null=True, editable=False, unique=True)

    goals = models.ManyToManyField(Goal, through='GoalRecord')

    def __unicode__(self):
        if self.registered_as:
            prefix = "registered"
        else:
            prefix = "anonymous"

        return u"%s subject #%d" % (prefix, self.id)

    def merge_into(self, othersubject):
        """Move the enrollments and goalrecords associated with this subject
        into the given othersubject, preserving the othersubject's
        enrollments in case of conflict."""

        other_gs = dict(((g.name, 1) for g in othersubject.goals.all()))
        
        for gr in self.goalrecord_set.all().select_related("goal"):
            if gr.goal.name not in other_gs:
                gr.subject = othersubject
                gr.save()
            else:
                gr.delete()


        other_exps = dict(( (e.experiment_id,1) for e in othersubject.enrollment_set.all() ))

        for e in self.enrollment_set.all():
            if e.experiment_id not in other_exps:
                e.subject = othersubject
                e.save()
            else:
                e.delete()

        self.delete()



class GoalRecord(models.Model):
    goal = models.ForeignKey(Goal)
    subject = models.ForeignKey(Subject)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    req_HTTP_REFERER = models.CharField(max_length=255, null=True, blank=True)
    req_REMOTE_ADDR = models.IPAddressField(null=True, blank=True)
    req_path = models.CharField(max_length=255, null=True, blank=True)

    extra = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        unique_together= (('subject', 'goal'),)
        # never record the same goal twice for a given subject

    @staticmethod
    def extract_request_info(request):
        return dict(
            req_HTTP_REFERER=request.META.get("HTTP_REFERER","")[:255],
            req_REMOTE_ADDR=request.META["REMOTE_ADDR"],
            req_path=request.path[:255])

    @classmethod
    def record(cls, subject, goalname, request_info, extra=None):
        logging.warn("Splango:goalrecord %r" % [subject, goalname, request_info, extra])
        goal, created = Goal.objects.get_or_create(name=goalname)

        gr,created = cls.objects.get_or_create(subject=subject, 
                                               goal=goal,
                                               defaults=request_info)

        if not(created) and not(gr.extra) and extra:
            # add my extra info to the existing goal record
            gr.extra = extra
            gr.save()

        return gr

    @classmethod
    def record_user_goal(cls, user, goalname):
        sub, created = Subject.objects.get_or_create(registered_as=user)
        cls.record(sub, goalname, {})

    def __unicode__(self):
        return u"%s by subject #%d" % (self.goal, self.subject_id)







class Enrollment(models.Model):
    """Identifies which variant a subject is assigned to in a given
    experiment."""
    subject = models.ForeignKey('splango.Subject', editable=False)
    experiment = models.ForeignKey('splango.Experiment', editable=False)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    variant = models.CharField(max_length=_NAME_LENGTH)
    
    class Meta:
        unique_together= (('subject', 'experiment'),)

    def __unicode__(self):
        return u"experiment '%s' subject #%d -- variant %s" % (self.experiment.name, self.subject_id, self.variant)


    


class Experiment(models.Model):
    """A named experiment."""
    name = models.CharField(max_length=_NAME_LENGTH, primary_key=True)
    variants = models.TextField() # one per line... lame and simple
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    subjects = models.ManyToManyField(Subject, through=Enrollment)
    
    def __unicode__(self):
        return self.name

    def set_variants(self, variantlist):
        self.variants = "\n".join(variantlist)

    def get_variants(self):
        return [ x for x in self.variants.split("\n") if x ]

    def get_random_variant(self):
        return random.choice(self.get_variants())

    def variants_commasep(self):
        return ",".join(self.get_variants())

    def get_variant_for(self, subject):
        sv, created = Enrollment.objects.get_or_create(
            subject=subject,
            experiment=self,
            defaults={
                "variant": self.get_random_variant()
                })
        return sv

    def enroll_subject_as_variant(self, subject, variant):
        sv, created = Enrollment.objects.get_or_create(
            subject=subject,
            experiment=self,
            defaults={
                "variant": variant
                })
        return sv
        


    @classmethod
    def declare(cls, name, variants):
        e,created = cls.objects.get_or_create(name=name, 
                                              defaults={
                "variants":"\n".join(variants) })
        return e


class ExperimentReport(models.Model):
    """A report on the results of an experiment."""
    experiment = models.ForeignKey(Experiment)
    title = models.CharField(max_length=100, blank=True)
    funnel = models.TextField(help_text="List the goals, in order and one per line, that constitute this report's funnel.")

    def __unicode__(self):
        return u"%s - %s" % (self.title, self.experiment.name)

    def get_funnel_goals(self):
        return [ x.strip() for x in self.funnel.split("\n") if x ]
    
    def generate(self):
        result = []
        exp = self.experiment

        variants = self.experiment.get_variants()
        goals = self.get_funnel_goals()

        # count initial participation
        variant_counts = []

        for v in variants:
            #variant_counts.append(exp.subjectvariant_set.filter(variant=v).aggregate(ct=Count("variant")).get("ct",0))
            variant_counts.append(
                dict(val=Enrollment.objects.filter(experiment=exp, variant=v).count(),
                     variant_name=v,
                     pct=None,
                     pct_cumulative=1,
                     pct_cumulative_round=100))
                


        result.append({ "goal": None, 
                        "variant_names": variants,
                        "variant_counts": variant_counts })

        for previ, goal in enumerate(goals):
            try:
                g = Goal.objects.get(name=goal)
            except Goal.DoesNotExist:
                logging.warn("Splango: No such goal <<%s>>." % goal)
                g = None

            variant_counts = []


            for vi, v in enumerate(variants):

                if g:
                    vcount = Enrollment.objects.filter(experiment=exp, 
                                                       variant=v, 
                                                       subject__goals=g
                                                       ).count()

                    prev_count = result[previ]["variant_counts"][vi]["val"]

                    if prev_count == 0:
                        pct = 0
                    else:
                        pct = float(vcount) / float(prev_count)

                else:
                    vcount = 0
                    pct = 0

                pct_cumulative = pct*result[previ]["variant_counts"][vi]["pct_cumulative"]

                variant_counts.append(dict(val=vcount,
                                           variant_name=variants[vi],
                                           pct=pct,
                                           pct_round=( "%0.2f" % (100*pct) ),
                                           pct_cumulative=pct_cumulative,
                                           pct_cumulative_round=( "%0.2f" % (100*pct_cumulative) ),
                                           )
                                      )


            result.append({ "goal": goal, "variant_counts": variant_counts })


        return result
