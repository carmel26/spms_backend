from django.contrib import admin
from .models import BlockchainRecord, SmartContract


@admin.register(BlockchainRecord)
class BlockchainRecordAdmin(admin.ModelAdmin):
    list_display = ['block_number', 'record_type', 'user', 'timestamp']
    list_filter = ['record_type', 'timestamp']
    search_fields = ['user__username', 'current_hash']
    readonly_fields = ['block_number', 'current_hash', 'previous_hash']


@admin.register(SmartContract)
class SmartContractAdmin(admin.ModelAdmin):
    list_display = ['name', 'contract_type', 'is_active', 'created_at']
    list_filter = ['contract_type', 'is_active']
