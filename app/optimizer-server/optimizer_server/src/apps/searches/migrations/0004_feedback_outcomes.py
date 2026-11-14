from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("searches", "0003_query_category")]
    operations = [
        migrations.RenameField(model_name="feedback", old_name="is_good", new_name="legacy_is_good"),
        migrations.AlterField(model_name="feedback", name="legacy_is_good", field=models.BooleanField(null=True, blank=True)),
        migrations.AddField(model_name="feedback", name="purchase_conversion", field=models.BooleanField(null=True, blank=True)),
        migrations.AddField(model_name="feedback", name="user_confirmed_outcome", field=models.BooleanField(null=True, blank=True)),
        migrations.AddField(model_name="feedback", name="user_stopped_following_up", field=models.BooleanField(null=True, blank=True)),
    ]
