from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunSQL(
        "DROP TRIGGER IF EXISTS audit_event_enum_guard;",
        reverse_sql=migrations.RunSQL.noop,
    ), migrations.RunSQL(
        """CREATE TRIGGER audit_event_enum_guard BEFORE INSERT ON audit_auditevent
        WHEN NOT (
          (NEW.category='asset' AND NEW.action IN ('created','updated','status_changed','deleted') AND NEW.result IN ('success','rejected','failed')) OR
          (NEW.category='authentication' AND NEW.action IN ('login','login_throttled','logout','password_changed') AND NEW.result IN ('success','rejected','failed')) OR
          (NEW.category='account' AND NEW.action IN ('user_created','user_updated','user_disabled','role_changed','password_reset') AND NEW.result IN ('success','rejected','failed')) OR
          (NEW.category='import' AND NEW.action='previewed' AND NEW.result IN ('success','rejected','failed')) OR
          (NEW.category='import' AND NEW.action='executed' AND NEW.result IN ('started','success','partial','failed','interrupted')) OR
          (NEW.category='export' AND NEW.action='previewed' AND NEW.result IN ('success','rejected','failed')) OR
          (NEW.category='export' AND NEW.action='generated' AND NEW.result IN ('started','success','failed')) OR
          (NEW.category='export' AND NEW.action='downloaded' AND NEW.result IN ('started','transferred','failed','interrupted')) OR
          (NEW.category='backup' AND NEW.action IN ('created','downloaded','deleted') AND NEW.result IN ('started','success','failed','transferred','interrupted','rejected')) OR
          (NEW.category='restore' AND NEW.action='validated' AND NEW.result IN ('success','rejected','failed')) OR
          (NEW.category='restore' AND NEW.action='restored' AND NEW.result IN ('started','success','aborted','rolled_back','recovery_required')) OR
          (NEW.category='security' AND NEW.action='authorization_denied' AND NEW.result='denied')
        ) BEGIN SELECT RAISE(ABORT, 'AUDIT_ENUM_INVALID'); END;""",
        reverse_sql="DROP TRIGGER IF EXISTS audit_event_enum_guard;",
    )]
