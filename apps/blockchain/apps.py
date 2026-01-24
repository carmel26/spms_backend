from django.apps import AppConfig


class BlockchainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.blockchain'
    
    def ready(self):
        """Import signals when app is ready"""
        import apps.blockchain.signals
