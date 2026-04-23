class PermissionManager:
    def __init__(self, owner):
        self.owner = owner

    def has_permission(self, category):
        level = self.owner.permission_level
        if level == "full":
            return True
        if level == "files":
            return category in ("query", "files", "media")
        return category == "query"

    def set_permission_level(self, level):
        normalized = str(level).strip().lower()
        if normalized not in self.owner.permission_levels:
            return False
        self.owner.permission_level = normalized
        self.owner.save_assistant_config()
        return True
