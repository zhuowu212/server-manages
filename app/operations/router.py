from . import control_models


class ControlRouter:
    control_names = {model._meta.model_name for model in (
        control_models.BackupCatalog, control_models.RestoreOperation,
        control_models.SessionEpoch, control_models.ControlConfirmation,
        control_models.ControlReceipt,
    )}

    def db_for_read(self, model, **hints):
        return "control" if model._meta.model_name in self.control_names else None

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        first = obj1._state.db == "control"
        second = obj2._state.db == "control"
        return first == second

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name in self.control_names:
            return db == "control"
        if db == "control":
            return False
        return None
