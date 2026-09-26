from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("edupi_noise_monitor", "0002_noisemonitorconfig_audio_input_device_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="noisemonitorconfig",
            name="auto_start",
            field=models.BooleanField(
                default=True,
                help_text="Start monitoring as soon as the plugin loads",
            ),
        ),
    ]
