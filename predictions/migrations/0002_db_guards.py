"""Veritabanı seviyesinde kurallar (PostgreSQL/Supabase) + yeni tablolarda RLS.

Sunucu kodu (services.py) aynı kuralları uygular; bu tetikleyiciler, uygulamayı atlayan her yola
(elle SQL, hatalı bir kod yolu, yarış durumu) karşı ikinci güvencedir. SQLite'ta (yerel test) hiçbir
şey yapılmaz; kurallar orada yalnızca servis katmanıyla sağlanır.

Kurallar:
  * Soru: sonuçlanmış/iptal edilmiş soru değişmez; ilk tahminden sonra başlık, ölçüt ve kapanış
    değişmez; sonuç kapanıştan önce açıklanamaz; doğru seçenek o soruya ait olmalı;
    tahmin almış soru silinemez.
  * Seçenek: ilk tahminden sonra eklenemez/değiştirilemez/silinemez; sonuçlanmış soruya eklenemez.
  * Tahmin: kapanıştan sonra eklenemez/değiştirilemez; soru sahibi kendi sorusuna tahmin yapamaz;
    seçenek soruya ait olmalı; puan yalnızca sonuçlanmış soruda, bir kez, doğru seçeneğe 10 verilir.
"""
from django.db import migrations

CORRECT_POINTS = 10

FORWARD = f"""
CREATE OR REPLACE FUNCTION predictions_guard_question() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $fn$
DECLARE
  has_predictions boolean;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF EXISTS (SELECT 1 FROM predictions_prediction WHERE question_id = OLD.id) THEN
      RAISE EXCEPTION 'Tahmin almis soru silinemez' USING ERRCODE = 'P0001';
    END IF;
    RETURN OLD;
  END IF;

  IF OLD.status <> 'open' THEN
    RAISE EXCEPTION 'Sonuclanan veya iptal edilen soru degistirilemez' USING ERRCODE = 'P0001';
  END IF;
  IF NEW.created_by_id <> OLD.created_by_id THEN
    RAISE EXCEPTION 'Sorunun sahibi degistirilemez' USING ERRCODE = 'P0001';
  END IF;

  has_predictions := EXISTS (SELECT 1 FROM predictions_prediction WHERE question_id = OLD.id);
  IF has_predictions AND (NEW.title <> OLD.title OR NEW.closes_at <> OLD.closes_at
                          OR NEW.resolution_criteria <> OLD.resolution_criteria) THEN
    RAISE EXCEPTION 'Ilk tahminden sonra baslik, olcut ve kapanis degistirilemez' USING ERRCODE = 'P0001';
  END IF;
  IF NEW.closes_at <> OLD.closes_at AND NEW.closes_at <= now() THEN
    RAISE EXCEPTION 'Kapanis zamani gelecekte olmali' USING ERRCODE = 'P0001';
  END IF;

  IF NEW.status = 'resolved' THEN
    IF NEW.closes_at > now() THEN
      RAISE EXCEPTION 'Sonuc kapanistan once aciklanamaz' USING ERRCODE = 'P0001';
    END IF;
    IF NEW.correct_choice_id IS NULL OR NOT EXISTS (
         SELECT 1 FROM predictions_choice WHERE id = NEW.correct_choice_id AND question_id = NEW.id) THEN
      RAISE EXCEPTION 'Dogru secenek bu soruya ait olmali' USING ERRCODE = 'P0001';
    END IF;
  END IF;
  RETURN NEW;
END
$fn$;
--SPLIT--
CREATE OR REPLACE FUNCTION predictions_guard_choice() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $fn$
DECLARE
  qid bigint;
BEGIN
  IF TG_OP = 'INSERT' THEN qid := NEW.question_id; ELSE qid := OLD.question_id; END IF;

  IF EXISTS (SELECT 1 FROM predictions_prediction WHERE question_id = qid) THEN
    RAISE EXCEPTION 'Ilk tahminden sonra secenekler degistirilemez' USING ERRCODE = 'P0001';
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.question_id <> OLD.question_id THEN
    RAISE EXCEPTION 'Secenegin sorusu degistirilemez' USING ERRCODE = 'P0001';
  END IF;
  IF TG_OP <> 'DELETE' AND EXISTS (SELECT 1 FROM predictions_question WHERE id = qid AND status <> 'open') THEN
    RAISE EXCEPTION 'Sonuclanan veya iptal edilen soruya secenek eklenemez' USING ERRCODE = 'P0001';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END
$fn$;
--SPLIT--
CREATE OR REPLACE FUNCTION predictions_guard_prediction() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $fn$
DECLARE
  q record;
  choice_question bigint;
BEGIN
  SELECT id, status, closes_at, created_by_id, correct_choice_id INTO q
    FROM predictions_question WHERE id = NEW.question_id;

  IF TG_OP = 'UPDATE' AND (NEW.question_id <> OLD.question_id OR NEW.user_id <> OLD.user_id) THEN
    RAISE EXCEPTION 'Tahminin sahibi ve sorusu degistirilemez' USING ERRCODE = 'P0001';
  END IF;

  IF TG_OP = 'INSERT' OR NEW.choice_id <> OLD.choice_id THEN
    IF q.status <> 'open' OR q.closes_at <= now() THEN
      RAISE EXCEPTION 'Tahmin suresi doldu' USING ERRCODE = 'P0001';
    END IF;
    IF q.created_by_id = NEW.user_id THEN
      RAISE EXCEPTION 'Kendi sorusuna tahmin yapilamaz' USING ERRCODE = 'P0001';
    END IF;
    SELECT question_id INTO choice_question FROM predictions_choice WHERE id = NEW.choice_id;
    IF choice_question IS DISTINCT FROM NEW.question_id THEN
      RAISE EXCEPTION 'Secenek bu soruya ait degil' USING ERRCODE = 'P0001';
    END IF;
  END IF;

  IF TG_OP = 'INSERT' THEN
    IF NEW.is_correct IS NOT NULL OR NEW.points_awarded <> 0 THEN
      RAISE EXCEPTION 'Puan elle verilemez' USING ERRCODE = 'P0001';
    END IF;
  ELSIF NEW.is_correct IS DISTINCT FROM OLD.is_correct OR NEW.points_awarded <> OLD.points_awarded THEN
    IF OLD.is_correct IS NOT NULL THEN
      RAISE EXCEPTION 'Puan bu soru icin zaten dagitildi' USING ERRCODE = 'P0001';
    END IF;
    IF q.status <> 'resolved' THEN
      RAISE EXCEPTION 'Sonuc aciklanmadan puan verilemez' USING ERRCODE = 'P0001';
    END IF;
    IF q.created_by_id = NEW.user_id THEN
      RAISE EXCEPTION 'Soru sahibi kendi sorusundan puan kazanamaz' USING ERRCODE = 'P0001';
    END IF;
    IF NEW.is_correct IS NULL OR NEW.is_correct <> (NEW.choice_id = q.correct_choice_id) THEN
      RAISE EXCEPTION 'Puan dogru secenekle eslesmiyor' USING ERRCODE = 'P0001';
    END IF;
    IF NEW.points_awarded <> (CASE WHEN NEW.is_correct THEN {CORRECT_POINTS} ELSE 0 END) THEN
      RAISE EXCEPTION 'Puan miktari hatali' USING ERRCODE = 'P0001';
    END IF;
  END IF;
  RETURN NEW;
END
$fn$;
--SPLIT--
DROP TRIGGER IF EXISTS predictions_guard_question_trg ON predictions_question;
--SPLIT--
CREATE TRIGGER predictions_guard_question_trg BEFORE UPDATE OR DELETE ON predictions_question
  FOR EACH ROW EXECUTE FUNCTION predictions_guard_question();
--SPLIT--
DROP TRIGGER IF EXISTS predictions_guard_choice_trg ON predictions_choice;
--SPLIT--
CREATE TRIGGER predictions_guard_choice_trg BEFORE INSERT OR UPDATE OR DELETE ON predictions_choice
  FOR EACH ROW EXECUTE FUNCTION predictions_guard_choice();
--SPLIT--
DROP TRIGGER IF EXISTS predictions_guard_prediction_trg ON predictions_prediction;
--SPLIT--
CREATE TRIGGER predictions_guard_prediction_trg BEFORE INSERT OR UPDATE ON predictions_prediction
  FOR EACH ROW EXECUTE FUNCTION predictions_guard_prediction();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS predictions_guard_prediction_trg ON predictions_prediction;
--SPLIT--
DROP TRIGGER IF EXISTS predictions_guard_choice_trg ON predictions_choice;
--SPLIT--
DROP TRIGGER IF EXISTS predictions_guard_question_trg ON predictions_question;
--SPLIT--
DROP FUNCTION IF EXISTS predictions_guard_prediction();
--SPLIT--
DROP FUNCTION IF EXISTS predictions_guard_choice();
--SPLIT--
DROP FUNCTION IF EXISTS predictions_guard_question();
"""


def _run(schema_editor, script):
    """Komutlar tek tek çalıştırılır (psycopg3 tek çağrıda birden çok komuta izin vermez)."""
    for statement in script.split("--SPLIT--"):
        if statement.strip():
            schema_editor.execute(statement.strip(), params=None)


def apply_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    _run(schema_editor, FORWARD)
    # Supabase'in otomatik REST API'sine kapalı kal: politika yok, RLS açık (Django `postgres` rolüyle bağlanır).
    for table in schema_editor.connection.introspection.table_names():
        schema_editor.execute(f"ALTER TABLE {schema_editor.quote_name(table)} ENABLE ROW LEVEL SECURITY", params=None)


def remove_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    _run(schema_editor, BACKWARD)


class Migration(migrations.Migration):
    dependencies = [("predictions", "0001_initial")]
    operations = [migrations.RunPython(apply_guards, remove_guards)]
