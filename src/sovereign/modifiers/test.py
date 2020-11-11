from sovereign.modifiers.lib import Modifier
from sovereign.context import template_context
from sovereign.utils import eds, templates


class Test(Modifier):
    def match(self):
        return True

    def apply(self):
        assert template_context
        assert eds
        assert templates
        return self.instance
