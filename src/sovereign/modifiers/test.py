from sovereign import template_context
from sovereign.modifiers.lib import Modifier
from sovereign.utils import eds, templates


class Test(Modifier):
    def match(self) -> bool:
        return True

    def apply(self) -> None:
        assert template_context
        assert eds
        assert templates
        self.instance["modifier_test_executed"] = True
