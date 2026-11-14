import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Reshape for the which_search / submit_feedback protocol:
    drop dispatch-outcome fields and client_metadata, feedback becomes one is_good per search."""

    dependencies = [
        ("searches", "0001_initial"),
    ]

    operations = [
        # Old feedback (0-1 scores, possibly several per search) doesn't map onto is_good.
        migrations.RunSQL("DELETE FROM searches_feedback", migrations.RunSQL.noop),
        migrations.RemoveField(model_name="search", name="client_metadata"),
        migrations.RemoveField(model_name="search", name="outcome_reported_at"),
        migrations.RemoveField(model_name="search", name="latency_ms"),
        migrations.RemoveField(model_name="search", name="num_results"),
        migrations.RemoveField(model_name="search", name="error"),
        migrations.AlterModelOptions(name="feedback", options={}),
        migrations.RemoveField(model_name="feedback", name="score"),
        migrations.RemoveField(model_name="feedback", name="comment"),
        migrations.AddField(
            model_name="feedback",
            name="is_good",
            field=models.BooleanField(default=False),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="feedback",
            name="search",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="feedback",
                to="searches.search",
            ),
        ),
        migrations.AlterField(
            model_name="feedback",
            name="created_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
