from __future__ import annotations

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import DatasetChangeAttachment, DatasetInstance, HistoricalImportBatch


def _delete_file(file_field) -> None:
    if not file_field:
        return
    name = getattr(file_field, "name", "") or ""
    if not name:
        return
    storage = file_field.storage
    if storage.exists(name):
        storage.delete(name)


def _delete_replaced_file(sender, instance, field_name: str) -> None:
    if not instance.pk:
        return
    try:
        previous = sender.objects.only(field_name).get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    old_field = getattr(previous, field_name)
    new_field = getattr(instance, field_name)

    old_name = getattr(old_field, "name", "") or ""
    new_name = getattr(new_field, "name", "") or ""

    if old_name and old_name != new_name:
        storage = old_field.storage
        if storage.exists(old_name):
            storage.delete(old_name)


@receiver(pre_save, sender=DatasetInstance)
def delete_replaced_instance_raw_file(sender, instance, **kwargs):
    _delete_replaced_file(sender, instance, "raw_file")


@receiver(post_delete, sender=DatasetInstance)
def delete_instance_raw_file(sender, instance, **kwargs):
    _delete_file(instance.raw_file)


@receiver(pre_save, sender=HistoricalImportBatch)
def delete_replaced_batch_source_file(sender, instance, **kwargs):
    _delete_replaced_file(sender, instance, "source_file")


@receiver(post_delete, sender=HistoricalImportBatch)
def delete_batch_source_file(sender, instance, **kwargs):
    _delete_file(instance.source_file)


@receiver(pre_save, sender=DatasetChangeAttachment)
def delete_replaced_change_attachment(sender, instance, **kwargs):
    _delete_replaced_file(sender, instance, "file")


@receiver(post_delete, sender=DatasetChangeAttachment)
def delete_change_attachment(sender, instance, **kwargs):
    _delete_file(instance.file)
