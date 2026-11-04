from django.db import migrations


def _public_tables(schema_editor):
    return schema_editor.connection.introspection.table_names()


def enable_rls(apps, schema_editor):
    """Supabase'in otomatik REST API'sinden erişimi kapatmak için tüm tablolarda RLS'i aç.

    Politika eklenmez: Django `postgres` rolüyle bağlanır (RLS'i atlar), anon/authenticated
    roller ise hiçbir satıra erişemez. PostgreSQL dışındaki veritabanlarında (SQLite) bir şey yapmaz.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in _public_tables(schema_editor):
        schema_editor.execute(f"ALTER TABLE {schema_editor.quote_name(table)} ENABLE ROW LEVEL SECURITY")


def disable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in _public_tables(schema_editor):
        schema_editor.execute(f"ALTER TABLE {schema_editor.quote_name(table)} DISABLE ROW LEVEL SECURITY")


class Migration(migrations.Migration):
    # Bu noktada var olan tüm tabloların oluşmuş olması için diğer uygulamaların son migration'larına bağlı.
    dependencies = [
        ("polls", "0002_vote"),
        ("accounts", "0001_initial"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("sessions", "0001_initial"),
    ]

    operations = [migrations.RunPython(enable_rls, disable_rls)]
