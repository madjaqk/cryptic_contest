# Generated by Django 2.0.4 on 2018-04-19 01:44

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

from apps.cryptics.models import Contest as ContestClass

def set_status(apps, schema_editor):
    Contest = apps.get_model("cryptics", "Contest")
    for contest in Contest.objects.all():
        if contest.active:
            contest.status = ContestClass.SUBMISSIONS
        else:
            contest.status = ContestClass.CLOSED
        contest.save()

class Migration(migrations.Migration):

    dependencies = [
        ('cryptics', '0005_auto_20180404_1807'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='status',
            field=models.CharField(choices=[('S', 'submissions'), ('V', 'voting'), ('C', 'closed')], default='S', max_length=1),
        ),
        migrations.AlterField(
            model_name='contest',
            name='winning_entry',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='contest_this_won', to='cryptics.Submission'),
        ),
        migrations.AlterField(
            model_name='contest',
            name='winning_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='contests_won', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='submission',
            name='likers',
            field=models.ManyToManyField(blank=True, related_name='clues_liked', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(set_status)
    ]
