from autoclasstoc import Section, is_method


class PublicMethods(Section):
    key = "public-methods-no-dunder"
    title = "Public methods"

    def predicate(self, name, attr, meta):
        del meta
        return is_method(name, attr) and not name.startswith("_")
