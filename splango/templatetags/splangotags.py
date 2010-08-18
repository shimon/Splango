from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

import logging

register = template.Library()


from splango.models import Goal, Subject, GoalRecord, Enrollment, Experiment, ExperimentReport

CTX_PREFIX = "__splango__experiment__"

class ExperimentNode(template.Node):
    def __init__(self, exp_name, variants):
        self.exp_name = exp_name
        self.variants = variants

    def render(self, context):
        if "request" not in context:
            raise template.TemplateSyntaxError("Use of splangotags requires the request context processor. Please add django.core.context_processors.request to your settings.TEMPLATE_CONTEXT_PROCESSORS.")

        request = context["request"]
        exp = request.experiments

        if not exp:
            raise template.TemplateSyntaxError("Use of splangotags requires the splango middleware. Please add splango.middleware.ExperimentsMiddleware to your settings.MIDDLEWARE_CLASSES.")

        expvariant = exp.declare_and_enroll(self.exp_name, self.variants)
        context[CTX_PREFIX + self.exp_name] = expvariant

        return "" # "exp: %s - you are %s" % (self.exp_name, expvariant)

class HypNode(template.Node):
    def __init__(self, exp_name, exp_variant, nodelist):
        self.exp_name = exp_name
        self.exp_variant = exp_variant
        self.nodelist = nodelist

#         print ' ++ instantiated HypNode (%s, %s)' % (self.exp_name,
#                                                      self.exp_variant)

    def render(self, context):
#         print ' == rendering HypNode (%s, %s)' % (self.exp_name,
#                                                   self.exp_variant)

        ctxvar = CTX_PREFIX + self.exp_name

        if ctxvar not in context:
            raise template.TemplateSyntaxError("Experiment %s has not yet been declared. Please declare it and supply variant names using an experiment tag before using hyp tags.")

        if self.exp_variant == context[ctxvar]:
            return self.nodelist.render(context)
        else:
            return ""

        return "[%s==%s]"%(self.exp_variant, context[ctxvar])+self.nodelist.render(context)+"[/%s]"%self.exp_variant

        return "HypNode: exp_name=%s, exp_variant=%s" % (self.exp_name,
                                                         self.exp_variant)
    


@register.tag
def experiment(parser, token):
    try:
        tag_name, exp_name, variants_label, variantstring = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, '%r tag requires exactly three arguments, e.g. {% experiment "signuptext" variants "control,free,trial" %}' % token.contents.split()[0]

    return ExperimentNode(exp_name.strip("\"'"), variantstring.strip("\"'").split(","))



@register.tag
def hyp(parser, token):
    try:
        tag_name, exp_name, exp_variant = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires exactly two arguments" % token.contents.split()[0]


#     print "*** hyp looking for next tag"
    #print "parser.tokens = %r" % [ t.contents for t in parser.tokens ]

    nodelist = parser.parse(("endhyp",))
    token = parser.next_token()

#     print " * hyp FOUND TOKEN %s" % token.contents
    parser.delete_first_token()
    #print "parser.tokens = %r" % [ t.contents for t in parser.tokens ]

    
    return HypNode(exp_name.strip("\"'"), exp_variant.strip("\"'"), nodelist)


# I couldn't make this work well. Probably needs much more thought to work like
# a switch statement. See:
# http://djangosnippets.org/snippets/967/
#
# @register.tag
# def elsehyp(parser, token):
#     try:
#         tag_name, exp_variant = token.split_contents()
#     except ValueError:
#         raise template.TemplateSyntaxError, "%r tag requires exactly one argument" % token.contents.split()[0]

#     #import pdb;pdb.set_trace()

#     print "*** elsehyp looking for next tag"
#     #print "parser.tokens = %r" % [ t.contents for t in parser.tokens ]
    
#     nodelist = parser.parse(("elsehyp","endhyp"))
   
#     return HypNode(None, exp_variant, nodelist)
