from django.db import migrations, models


class Migration(migrations.Migration):
    """Bring the stored default in line with the service default.

    Both were different before, so a panel with no saved configuration came up
    on the rotation the service defaulted to while a panel with one came up on
    0 — a display on its side, with no setting in the interface to correct it.

    Default only: an existing row keeps whatever rotation it holds, because
    that row is what the panel is initialised from and changing it here would
    move a display someone may already have aligned.
    """

    dependencies = [
        ("lcd_display", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lcdconfig",
            name="rotation",
            field=models.IntegerField(
                choices=[
                    (0, "0 degrees"),
                    (90, "90 degrees"),
                    (180, "180 degrees"),
                    (270, "270 degrees"),
                ],
                default=90,
                help_text="Display rotation",
            ),
        ),
    ]
