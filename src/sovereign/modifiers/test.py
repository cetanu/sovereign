from sovereign.modifiers.lib import Modifier
from sovereign.utils import eds, templates
from sovereign.configuration import TEMPLATE_CONTEXT


class Test(Modifier):
    def match(self) -> bool:
        return True

    def apply(self) -> None:
        assert TEMPLATE_CONTEXT
        assert eds
        assert templates
        self.instance["modifier_test_executed"] = True
