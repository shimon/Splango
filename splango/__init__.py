from django.conf import settings

import logging
from django.utils.encoding import smart_unicode
from django.core.urlresolvers import reverse, NoReverseMatch

from splango.models import Subject, Experiment, Enrollment, GoalRecord

SPLANGO_STATE = "SPLANGO_STATE"
SPLANGO_SUBJECT = "SPLANGO_SUBJECT"
SPLANGO_QUEUED_UPDATES = "SPLANGO_QUEUED_UPDATES"
S_UNKNOWN = "UNKNOWN"
S_HUMAN = "HUMAN"

# borrowed from debug_toolbar
_HTML_TYPES = ('text/html', 'application/xhtml+xml')

# borrowed from debug_toolbar
def replace_insensitive(string, target, replacement):
    """
    Similar to string.replace() but is case insensitive
    Code borrowed from: http://forums.devshed.com/python-programming-11/case-insensitive-string-replace-490921.html
    """
    no_case = string.lower()
    index = no_case.rfind(target.lower())
    if index >= 0:
        return string[:index] + replacement + string[index + len(target):]
    else: # no results so return the original string
        return string




class RequestExperimentManager:

    def __init__(self, request):
        #logging.debug("REM init")
        self.request = request
        self.user_at_init = request.user
        self.queued_actions = []

        if self.request.session.get(SPLANGO_STATE) is None:
            self.request.session[SPLANGO_STATE] = S_UNKNOWN
            
            if self.is_first_visit():
                
                logging.info("SPLANGO! First visit!")

                first_visit_goalname = getattr(settings,
                                               "SPLANGO_FIRST_VISIT_GOAL", 
                                               None)

                if first_visit_goalname:
                    self.log_goal(first_visit_goalname)

    def enqueue(self, action, params):
        self.queued_actions.append( (action, params) )


    def process_from_queue(self, action, params):
        logging.info("SPLANGO! dequeued: %s (%s)" % (str(action), repr(params)))

        if action == "enroll":
            exp = Experiment.objects.get(name=params["exp_name"])
            exp.enroll_subject_as_variant(self.get_subject(),
                                          params["variant"])

        elif action == "log_goal":
            g = GoalRecord.record(self.get_subject(), 
                                  params["goal_name"], 
                                  params["request_info"],
                                  extra=params.get("extra"))

            logging.info("SPLANGO! goal! %s" % str(g))


        else:
            raise RuntimeError("Unknown queue action '%s'." % action)


    def is_first_visit(self):
        r = self.request

        if r.user.is_authenticated():
            return False

        ref = r.META.get("HTTP_REFERER", "").lower()

        if not ref: # if no referer, then musta just typed it in
            return True

        if ref.startswith("http://"):
            ref = ref[7:]
        elif ref.startswith("https://"):
            ref = ref[8:]

        return not(ref.startswith(r.get_host()))


    def render_js(self):
        logging.info("SPLANGO! render_js")

        prejs = ""
        postjs = ""

        if settings.DEBUG:
            prejs = "try { "
            postjs = ' } catch(e) { alert("DEBUG notice: Splango encountered a javascript error when attempting to confirm this user as a human. Is jQuery loaded?\\n\\nYou may notice inconsistent experiment enrollments until this is fixed.\\n\\nDetails:\\n"+e.toString()); }'

        try:
            url = reverse("splango-confirm-human")
        except NoReverseMatch:
            url = "/splango/confirm_human/"

        return """<script type='text/javascript'>%sjQuery.get("%s");%s</script>""" % (prejs, url, postjs)
        

    def confirm_human(self, reqdata=None):
        logging.info("SPLANGO! Human confirmed!")
        self.request.session[SPLANGO_STATE] = S_HUMAN

        for (action, params) in self.request.session.get(SPLANGO_QUEUED_UPDATES, []):
            self.process_from_queue(action, params)
                

    def finish(self, response):
        curstate = self.request.session.get(SPLANGO_STATE, S_UNKNOWN)

        #logging.info("SPLANGO! finished... state=%s" % curstate)

        curuser = self.request.user

        if self.user_at_init != curuser:
            logging.info("SPLANGO! user status changed over request: %s --> %s" % (str(self.user_at_init), str(curuser)))

            if not(curuser.is_authenticated()):
                # User logged out. It's a new session, nothing special.
                pass

            else:
                # User has just logged in (or registered).
                # We'll merge the session's current Subject with 
                # an existing Subject for this user, if exists,
                # or simply set the subject.registered_as field.

                self.request.session[SPLANGO_STATE] = S_HUMAN
                # logging in counts as being proved a human

                old_subject = self.request.session.get(SPLANGO_SUBJECT)

                try:
                    existing_subject = Subject.objects.get(registered_as=curuser)
                    # there is an existing registered subject!
                    if old_subject and old_subject.id != existing_subject.id:
                        # merge old subject's activity into new
                        old_subject.merge_into(existing_subject)

                    # whether we had an old_subject or not, we must 
                    # set session to use our existing_subject
                    self.request.session[SPLANGO_SUBJECT] = existing_subject

                except Subject.DoesNotExist:
                    # promote current subject to registered!
                    sub = self.get_subject()
                    sub.registered_as = curuser
                    sub.save()

        if curstate == S_HUMAN:
            # run anything in my queue
            for (action, params) in self.queued_actions:
                self.process_from_queue(action, params)
            self.queued_actions = []

        else:
            # shove queue into session
            self.request.session.setdefault(SPLANGO_QUEUED_UPDATES, []).extend(self.queued_actions)
            self.queued_actions = []

            # and include JS if suitable for this response.
            if response['Content-Type'].split(';')[0] in _HTML_TYPES:
                response.content = replace_insensitive(smart_unicode(response.content), u'</body>', smart_unicode(self.render_js() + u'</body>'))

        return response
        
        

    def get_subject(self):
        assert self.request.session[SPLANGO_STATE] == S_HUMAN, "Hey, you can't call get_subject until you know the subject is a human!"

        sub = self.request.session.get(SPLANGO_SUBJECT)

        if not sub:
            sub = self.request.session[SPLANGO_SUBJECT] = Subject()
            sub.save()
            logging.info("SPLANGO! created subject: %s" % str(sub))
        
        return sub


    def declare_and_enroll(self, exp_name, variants):
        e = Experiment.declare(exp_name, variants)

        if self.request.session[SPLANGO_STATE] != S_HUMAN:
            logging.info("SPLANGO! choosing new random variant for non-human")
            v = e.get_random_variant()
            self.enqueue("enroll", { "exp_name": e.name, "variant": v })

        else:
            sub = self.get_subject()
            sv = e.get_variant_for(sub)
            v = sv.variant
            logging.info("SPLANGO! got variant %s for subject %s" % (str(v),str(sub)))

        return v


    def log_goal(self, goal_name, extra=None):

        request_info = GoalRecord.extract_request_info(self.request)

        self.enqueue("log_goal", { "goal_name": goal_name,
                                   "request_info": request_info,
                                   "extra": extra })

